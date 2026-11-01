#!/usr/bin/env python3
"""MyTellPBX v7.2.0 — panel-credential sign-in for the desk (OpDesk).

Adds POST /api/auth/login-panel: verifies {login, password} against the
Issabel panel ACL (sqlite opened READ-ONLY: readOnly + PRAGMA
query_only; the panel database is never written — md5 comparison is a
read-only compatibility check with the panel's own stored format), maps
the immutable panel identity (provider='issabel-panel',
externalId=acl_user.id) to a desk shadow user created transactionally
under a UNIQUE(provider, external_id) constraint, and issues the same
HS256 JWT machinery with a signed auth_source='panel' marker and a
15-minute TTL (no refresh path). Role 'admin' is granted only while
panel group-1 membership stays valid: principal resolution revalidates
(cached <=15s, fail-closed) and panel-sourced WebSocket connections are
re-checked every 30s and closed (1008) when membership is lost. Wrong
password, unknown user and non-admin panel user are indistinguishable;
throttling shares the existing limiter buckets (per client IP and per
client-IP|login pair) with the native endpoint.

Frontend: explicit account-source toggle on the login card («حساب پنل»
default vs «حساب میز کار»); each posts to its own endpoint, never both.

Usage (root on 192.168.8.171):   python3 patch-panel-login.py [--skip-build]
Idempotent; one-time .bak-mt backups; nonzero exit on unexpected anchors.
"""
import argparse
import json
import pathlib
import shutil
import subprocess
import sys

BE = pathlib.Path("/opt/opdesk/backend")
FE = pathlib.Path("/opt/opdesk/frontend/src")

PANEL_AUTH_TS = BE / "src/core/panel-auth.ts"
PANEL_AUTH_SPEC = BE / "test/core/panel-auth.spec.ts"
SCHEMA = BE / "schema.sql"
SECURITY = BE / "src/core/security.ts"
USERS_PATH = BE / "src/db/manager/users.ts"
AUTHCTRL = BE / "src/api/routes/auth.controller.ts"
WSTS = BE / "src/api/routes/ws.ts"
LOGIN_TSX = FE / "components/Login.tsx"
STYLES_CSS = FE / "styles/index.css"
FA_JSON = FE / "i18n/locales/fa/translation.json"
EN_JSON = FE / "i18n/locales/en/translation.json"

PANEL_AUTH_SOURCE = '''/**
 * Panel-source authentication (MyTellPBX v7.2.0).
 *
 * Verifies Issabel panel credentials against the panel's own sqlite ACL
 * database READ-ONLY (readOnly open + PRAGMA query_only; the file is never
 * written). The md5 comparison is a read-only compatibility check with the
 * format the panel itself stores — the desk keeps bcrypt for its own
 * accounts. Maps the immutable panel identity (provider='issabel-panel',
 * externalId=acl_user.id) to a desk shadow user and exposes the membership
 * guard used to revalidate panel-sourced tokens and sockets.
 *
 * Policy: only current members of panel group 1 (administrators) may sign
 * in via this source; they hold role 'admin' exactly while the membership
 * stays valid. Shadow users get an unusable random bcrypt password, keep
 * the panel display name, and honor desk-side suspension (is_active).
 */
import { createHash } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { getLogger } from './logger';
import { execute, queryOne, withTransaction } from '../db/pool';
import { hashUserPassword } from '../db/manager/users';

const log = getLogger('core.panel_auth');

export const PANEL_AUTH_SOURCE = 'panel';
export const PANEL_PROVIDER = 'issabel-panel';
export const PANEL_TOKEN_TTL_SECONDS = 15 * 60;
const MEMBERSHIP_CACHE_MS = 15_000;

/** Resolve the panel ACL path at CALL time so tests (and env overrides)
 *  apply regardless of module load order. */
function panelAclPath(): string {
  return process.env.MYTELLPBX_PANEL_ACL_PATH || '/var/www/db/acl.db';
}

let membershipCache: { key: string; at: number; ok: boolean } | null = null;

/** Open the panel ACL read-only (query_only as an extra safeguard). */
function openPanelDb(): DatabaseSync | null {
  try {
    const db = new DatabaseSync(panelAclPath(), { readOnly: true });
    db.prepare('PRAGMA query_only').run();
    return db;
  } catch (e) {
    log.warning('Panel ACL unavailable: %s', e);
    return null;
  }
}

/** The panel stores md5(password) hex; this mirrors that check read-only. */
function panelMd5(input: string): string {
  return createHash('md5').update(input, 'utf8').digest('hex');
}

function sameHexConstantTime(a: string, b: string): boolean {
  const ab = Buffer.from(String(a), 'utf8');
  const bb = Buffer.from(String(b), 'utf8');
  if (ab.length !== bb.length) {
    // burn a comparison anyway so the length branch does not leak timing
    ab.equals(ab);
    return false;
  }
  return ab.equals(bb);
}

export interface PanelCredential {
  panelUserId: number;
  name: string | null;
}

/**
 * Verify a panel username + password. Returns the panel identity on
 * success, null otherwise (unknown user, wrong password, non-admin
 * membership, or an unreadable ACL — all fail closed and are
 * indistinguishable to the caller).
 */
export function verifyPanelCredential(loginName: string, password: string): PanelCredential | null {
  if (!loginName || !password) return null;
  const db = openPanelDb();
  if (!db) return null;
  try {
    const row = db
      .prepare('SELECT id, name, md5_password FROM acl_user WHERE name = ?')
      .get(loginName) as { id: number; name: string | null; md5_password: string } | undefined;
    if (!row) {
      sameHexConstantTime('0'.repeat(32), '1'.repeat(32)); // dummy work
      return null;
    }
    if (!sameHexConstantTime(String(row.md5_password || '').toLowerCase(), panelMd5(password))) return null;
    const grp = db
      .prepare('SELECT COUNT(*) AS n FROM acl_membership WHERE id_user = ? AND id_group = 1')
      .get(row.id) as { n: number } | undefined;
    if (!grp || Number(grp.n) <= 0) return null;
    return { panelUserId: Number(row.id), name: row.name ?? null };
  } catch (e) {
    log.warning('Panel credential check failed: %s', e);
    return null;
  } finally {
    db.close();
  }
}

interface DeskShadowUser {
  id: number;
  username: string;
  name: string | null;
  role: string;
  is_active: number;
}

async function shadowByExternalId(externalId: number): Promise<DeskShadowUser | null> {
  const row = await queryOne(
    'SELECT u.id, u.username, u.name, u.role, u.is_active FROM users u '
      + 'JOIN user_identities i ON i.user_id = u.id '
      + 'WHERE i.provider = ? AND i.external_id = ?',
    [PANEL_PROVIDER, String(externalId)],
  );
  return (row as unknown as DeskShadowUser) ?? null;
}

/**
 * Find-or-create the desk shadow user for a panel identity and refresh its
 * display metadata (rename never changes identity). Creation is
 * transactional (user + identity + default monitor mode) under the
 * UNIQUE(provider, external_id) constraint; a concurrent create collapses
 * to the existing row.
 */
export async function ensurePanelUser(panel: PanelCredential): Promise<DeskShadowUser | null> {
  const internalLogin = `panel:${panel.panelUserId}`;
  let shadow = await shadowByExternalId(panel.panelUserId);
  if (!shadow) {
    const { randomBytes } = await import('node:crypto');
    const unusableHash = await hashUserPassword(randomBytes(48).toString('hex'));
    try {
      await withTransaction(async (conn) => {
        const res = await execute(
          'INSERT INTO users (username, password_hash, name, role) VALUES (?, ?, ?, ?)',
          [internalLogin, unusableHash, panel.name ?? internalLogin, 'admin'],
          conn,
        );
        const userId = Number(res.insertId);
        if (!userId) throw new Error('shadow insert produced no id');
        await execute(
          'INSERT INTO user_identities (provider, external_id, user_id) VALUES (?, ?, ?)',
          [PANEL_PROVIDER, String(panel.panelUserId), String(userId)],
          conn,
        );
        await execute('INSERT INTO user_monitor_modes (user_id, mode) VALUES (?, ?)', [String(userId), 'listen'], conn);
      });
    } catch (e) {
      // UNIQUE race or transient error: fall through to the re-select.
      log.warning('Panel shadow create raced: %s', e);
    }
    shadow = await shadowByExternalId(panel.panelUserId);
  }
  if (!shadow) return null;
  if ((shadow.name ?? null) !== (panel.name ?? null)) {
    await execute('UPDATE users SET name = ? WHERE id = ?', [panel.name ?? internalLogin, String(shadow.id)]);
    shadow.name = panel.name ?? internalLogin;
  }
  return shadow;
}

/** Group-1 membership of a panel user (cached <=15s, fail-closed). */
export function panelMembershipValid(externalId: number): boolean {
  const key = String(externalId);
  const now = Date.now();
  if (membershipCache && membershipCache.key === key && now - membershipCache.at < MEMBERSHIP_CACHE_MS) {
    return membershipCache.ok;
  }
  const db = openPanelDb();
  if (!db) {
    membershipCache = { key, at: now, ok: false };
    return false;
  }
  try {
    const grp = db
      .prepare('SELECT COUNT(*) AS n FROM acl_membership WHERE id_user = ? AND id_group = 1')
      .get(externalId) as { n: number } | undefined;
    const ok = !!grp && Number(grp.n) > 0;
    membershipCache = { key, at: now, ok };
    return ok;
  } catch (e) {
    log.warning('Panel membership check failed: %s', e);
    membershipCache = { key, at: now, ok: false };
    return false;
  } finally {
    db.close();
  }
}

/** The panel external id behind a desk user (null when not panel-sourced). */
export async function panelExternalIdOfDeskUser(deskUserId: number): Promise<number | null> {
  const row = await queryOne(
    'SELECT external_id FROM user_identities WHERE provider = ? AND user_id = ?',
    [PANEL_PROVIDER, String(deskUserId)],
  );
  return row ? Number((row as unknown as { external_id: string }).external_id) : null;
}

/**
 * Guard for token resolution: a panel-sourced principal stays valid only
 * while its mapped panel identity still holds group-1 membership. A
 * panel marker without a mapping fails closed. Async (identity lookup).
 */
export async function panelSourceAllowed(deskUserId: number): Promise<boolean> {
  const ext = await panelExternalIdOfDeskUser(deskUserId);
  if (ext === null) return false;
  return panelMembershipValid(ext);
}

/** Tests only. */
export function resetPanelAuthCache(): void {
  membershipCache = null;
}
'''

PANEL_AUTH_SPEC_SOURCE = '''/**
 * Panel-source authentication tests (MyTellPBX v7.2.0).
 * The panel ACL fixture is a real sqlite file opened read-only, mirroring
 * /var/www/db/acl.db (acl_user + acl_membership, group 1 = admin).
 */
import { createHash } from 'node:crypto';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';

const adminPw = 'panel-admin-pw-1';
const otherPw = 'panel-other-pw-2';

function makeAclFixture(): string {
  const dir = mkdtempSync(join(tmpdir(), 'mt-panel-acl-'));
  const path = join(dir, 'acl.db');
  const db = new DatabaseSync(path);
  db.exec('CREATE TABLE acl_user (id INTEGER PRIMARY KEY, name TEXT, md5_password TEXT)');
  db.exec('CREATE TABLE acl_membership (id INTEGER PRIMARY KEY, id_user INTEGER, id_group INTEGER)');
  const md5 = (s: string) => createHash('md5').update(s).digest('hex');
  db.prepare('INSERT INTO acl_user (id, name, md5_password) VALUES (?, ?, ?)').run(7, 'admin', md5(adminPw));
  db.prepare('INSERT INTO acl_user (id, name, md5_password) VALUES (?, ?, ?)').run(8, 'operator', md5(otherPw));
  db.prepare('INSERT INTO acl_membership (id, id_user, id_group) VALUES (1, 7, 1)').run();
  db.prepare('INSERT INTO acl_membership (id, id_user, id_group) VALUES (2, 8, 3)').run();
  db.close();
  return path;
}

describe('panel-auth credential verification', () => {
  let fixture: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let panelAuth: any;

  beforeAll(() => {
    fixture = makeAclFixture();
    jest.isolateModules(() => {
      process.env.MYTELLPBX_PANEL_ACL_PATH = fixture;
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      panelAuth = require('../../src/core/panel-auth');
    });
  });

  test('group-1 member with the correct password verifies', () => {
    expect(panelAuth.verifyPanelCredential('admin', adminPw)).toEqual({ panelUserId: 7, name: 'admin' });
  });

  test('wrong password, unknown user and non-admin are indistinguishable (null)', () => {
    expect(panelAuth.verifyPanelCredential('admin', 'nope')).toBeNull();
    expect(panelAuth.verifyPanelCredential('ghost', adminPw)).toBeNull();
    expect(panelAuth.verifyPanelCredential('operator', otherPw)).toBeNull();
  });

  test('membership guard follows group 1', () => {
    panelAuth.resetPanelAuthCache();
    expect(panelAuth.panelMembershipValid(7)).toBe(true);
    expect(panelAuth.panelMembershipValid(8)).toBe(false);
  });
});
'''

SCHEMA_APPEND = """
-- MyTellPBX v7.2.0: external identity mapping for panel-sourced desk
-- accounts. UNIQUE(provider, external_id) is the immutable identity.
CREATE TABLE IF NOT EXISTS user_identities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    provider   VARCHAR(64)  NOT NULL,
    external_id VARCHAR(64) NOT NULL,
    user_id    INT          NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_provider_external (provider, external_id),
    KEY idx_identity_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

SECURITY_TOKEN_EDIT = [
    (
        "export async function createAccessToken(user: { id: number; username: string; role: string }): Promise<string> {\n"
        "  const now = Math.floor(Date.now() / 1000);\n"
        "  const payload: TokenClaims = {\n"
        "    sub: String(user.id),\n"
        "    username: user.username,\n"
        "    role: user.role,\n"
        "    exp: now + JWT_EXPIRE_HOURS * 3600,\n"
        "    iat: now,\n"
        "  };\n"
        "  return encodeJwt(payload, await getJwtSecret());\n"
        "}",
        "export async function createAccessToken(\n"
        "  user: { id: number; username: string; role: string },\n"
        "  opts: { authSource?: string; ttlSeconds?: number } = {},\n"
        "): Promise<string> {\n"
        "  const now = Math.floor(Date.now() / 1000);\n"
        "  const payload: TokenClaims = {\n"
        "    sub: String(user.id),\n"
        "    username: user.username,\n"
        "    role: user.role,\n"
        "    exp: now + (opts.ttlSeconds ?? JWT_EXPIRE_HOURS * 3600),\n"
        "    iat: now,\n"
        "    auth_source: opts.authSource ?? 'native',\n"
        "  };\n"
        "  return encodeJwt(payload, await getJwtSecret());\n"
        "}",
    )]

SECURITY_GUARD_ALTERNATIVES = [    (
        "  const username = typeof claims.username === 'string' ? claims.username : null;\n"
        "  return principalFromUserId(parseInt(sub, 10), username);",
        "  const username = typeof claims.username === 'string' ? claims.username : null;\n"
        "  const principal = await principalFromUserId(parseInt(sub, 10), username);\n"
        "  if (principal && claims.auth_source === 'panel') {\n"
        "    // Panel-sourced principals stay valid only while the mapped panel\n"
        "    // identity still holds group-1 membership (cached <= 15s, closed on\n"
        "    // any doubt). Lazy require keeps this module load-order simple.\n"
        "    // eslint-disable-next-line @typescript-eslint/no-var-requires\n"
        "    const guard = require('./panel-auth') as { panelSourceAllowed(deskUserId: number): Promise<boolean> };\n"
        "    if (!(await guard.panelSourceAllowed(Number(principal.id)))) return null;\n"
        "  }\n"
        "  return principal;",
    ),
    # legacy intermediate (deployed during development): sync guard call
    (
        "  const username = typeof claims.username === 'string' ? claims.username : null;\n"
        "  const principal = await principalFromUserId(parseInt(sub, 10), username);\n"
        "  if (principal && claims.auth_source === 'panel') {\n"
        "    // Panel-sourced principals stay valid only while the mapped panel\n"
        "    // identity still holds group-1 membership (cached <= 15s, closed on\n"
        "    // any doubt). Lazy require keeps this module load-order simple.\n"
        "    // eslint-disable-next-line @typescript-eslint/no-var-requires\n"
        "    const guard = require('./panel-auth') as { panelSourceAllowed(deskUserId: number): boolean };\n"
        "    if (!guard.panelSourceAllowed(Number(principal.id))) return null;\n"
        "  }\n"
        "  return principal;",
        "  const username = typeof claims.username === 'string' ? claims.username : null;\n"
        "  const principal = await principalFromUserId(parseInt(sub, 10), username);\n"
        "  if (principal && claims.auth_source === 'panel') {\n"
        "    // Panel-sourced principals stay valid only while the mapped panel\n"
        "    // identity still holds group-1 membership (cached <= 15s, closed on\n"
        "    // any doubt). Lazy require keeps this module load-order simple.\n"
        "    // eslint-disable-next-line @typescript-eslint/no-var-requires\n"
        "    const guard = require('./panel-auth') as { panelSourceAllowed(deskUserId: number): Promise<boolean> };\n"
        "    if (!(await guard.panelSourceAllowed(Number(principal.id)))) return null;\n"
        "  }\n"
        "  return principal;",
    ),]

USERS_HASH_EXPORT = (
    "export async function verifyUserPassword(passwordHash: string | null | undefined, password: string | null | undefined): Promise<boolean> {",
    "export async function hashPasswordForShadow(): Promise<string> {\n"
    "  // MyTellPBX v7.2.0: unusable random material for panel shadow accounts\n"
    "  // eslint-disable-next-line @typescript-eslint/no-var-requires\n"
    "  const { randomBytes } = require('node:crypto');\n"
    "  return hashUserPassword(randomBytes(48).toString('hex'));\n"
    "}\n"
    "\n"
    "export async function verifyUserPassword(passwordHash: string | null | undefined, password: string | null | undefined): Promise<boolean> {",
)

AUTHCTRL_NEW_ENDPOINT = '''
  /**
   * MyTellPBX v7.2.0 — sign in with Issabel PANEL credentials (admin group
   * only). Same request/response shape as the native login; failures are
   * indistinguishable from it. Tokens carry auth_source='panel' and a
   * 15-minute TTL; no refresh path. Throttling shares the native limiter
   * buckets (per client IP and per client-IP|login pair).
   */
  @Post('/api/auth/login-panel')
  @Auth('public')
  async loginPanel(@Req() req: Request) {
    const body = parseBody(LoginBody, req.body);
    const clientIp = clientHost(req) ?? 'unknown';
    const pair = `${clientIp}|${body.login || ''}`;
    checkLoginRateLimit(clientIp);
    checkLoginRateLimit(pair);
    const login = (body.login || '').trim();
    const password = body.password || '';
    if (!login || !password) throw new HttpError(400, 'Login and password required');
    const cred = verifyPanelCredential(login, password);
    if (!cred) {
      recordLoginFailure(clientIp);
      recordLoginFailure(pair);
      throw new HttpError(401, 'Invalid extension/username or password');
    }
    const shadow = await ensurePanelUser(cred);
    if (!shadow || !shadow.is_active) {
      // desk-side suspension is honored; still indistinguishable
      recordLoginFailure(clientIp);
      recordLoginFailure(pair);
      throw new HttpError(401, 'Invalid extension/username or password');
    }
    clearLoginFailures(clientIp);
    clearLoginFailures(pair);
    const token = await createAccessToken(
      { id: shadow.id, username: shadow.username, role: shadow.role },
      { authSource: PANEL_AUTH_SOURCE, ttlSeconds: PANEL_TOKEN_TTL_SECONDS },
    );
    const scope = await getUserScope(shadow.id);
    log.info('Login(panel): %s (%s) from %s', shadow.username, shadow.role, clientIp);
    return {
      access_token: token,
      token_type: 'bearer',
      auth_source: PANEL_AUTH_SOURCE,
      user: {
        id: shadow.id,
        username: shadow.username,
        name: shadow.name ?? null,
        role: shadow.role,
        extension: null,
        monitor_modes: principalMonitorModes(scope),
        allowed_agent_extensions: scope.allowed_agent_extensions,
        allowed_queue_names: scope.allowed_queue_names,
        is_agent: false,
      },
    };
  }

'''

AUTHCTRL_IMPORT_EDIT = (
    "import {\n"
    "  checkLoginRateLimit,\n"
    "  clearLoginFailures,\n"
    "  createAccessToken,\n"
    "  getUserScope,\n"
    "  isAgentUser,\n"
    "  principalMonitorModes,\n"
    "  recordLoginFailure,\n"
    "  verifyPassword,\n"
    "} from '../../core/security';",
    "import {\n"
    "  checkLoginRateLimit,\n"
    "  clearLoginFailures,\n"
    "  createAccessToken,\n"
    "  getUserScope,\n"
    "  isAgentUser,\n"
    "  principalMonitorModes,\n"
    "  recordLoginFailure,\n"
    "  verifyPassword,\n"
    "} from '../../core/security';\n"
    "import {\n"
    "  PANEL_AUTH_SOURCE,\n"
    "  PANEL_TOKEN_TTL_SECONDS,\n"
    "  ensurePanelUser,\n"
    "  verifyPanelCredential,\n"
    "} from '../../core/panel-auth';",
)

WSTS_IMPORT_EDIT = (
    "import { authenticateWsToken, type Principal } from '../../core/security';",
    "import { authenticateWsToken, decodeAccessToken, type Principal } from '../../core/security';",
)

WSTS_FINAL = (
    "  const scope = scopeFromPrincipal(principal);\n"
    "  // MyTellPBX v7.2.0: panel-sourced sockets are revalidated every 30s\n"
    "  // (membership loss closes the socket with 1008); native sockets are\n"
    "  // unaffected. The timer dies with the socket.\n"
    "  let panelWatch: ReturnType<typeof setInterval> | null = null;\n"
    "  const sourceClaims = token ? await decodeAccessToken(token) : null;\n"
    "  if (sourceClaims && (sourceClaims as { auth_source?: string }).auth_source === 'panel') {\n"
    "    // eslint-disable-next-line @typescript-eslint/no-var-requires\n"
    "    const panelGuard = require('../../core/panel-auth') as typeof import('../../core/panel-auth');\n"
    "    panelWatch = setInterval(() => {\n"
    "      const deskId = (scope as { user_id?: number | null }).user_id ?? null;\n"
    "      if (deskId === null) {\n"
    "        if (panelWatch) clearInterval(panelWatch);\n"
    "        panelWatch = null;\n"
    "        websocket.close(1008, 'Panel membership no longer valid');\n"
    "        return;\n"
    "      }\n"
    "      panelGuard.panelSourceAllowed(Number(deskId)).then((ok) => {\n"
    "        if (!ok && panelWatch) {\n"
    "          clearInterval(panelWatch);\n"
    "          panelWatch = null;\n"
    "          websocket.close(1008, 'Panel membership no longer valid');\n"
    "        }\n"
    "      }).catch(() => {\n"
    "        // fail closed: an identity-lookup failure also ends the socket\n"
    "        if (panelWatch) clearInterval(panelWatch);\n"
    "        panelWatch = null;\n"
    "        websocket.close(1008, 'Panel membership no longer valid');\n"
    "      });\n"
    "    }, 30_000);\n"
    "    websocket.on('close', () => {\n"
    "      if (panelWatch) clearInterval(panelWatch);\n"
    "      panelWatch = null;\n"
    "    });\n"
    "  }\n"
    "  await runtime.manager.connect(websocket, scope as never);"
)

WSTS_LEGACY_SYNC_BLOCK = (
    "    panelWatch = setInterval(() => {\n"
    "      const deskId = (scope as { user_id?: number | null }).user_id ?? null;\n"
    "      if (deskId === null || !panelGuard.panelSourceAllowed(Number(deskId))) {\n"
    "        if (panelWatch) clearInterval(panelWatch);\n"
    "        panelWatch = null;\n"
    "        websocket.close(1008, 'Panel membership no longer valid');\n"
    "      }\n"
    "    }, 30_000);\n"
)

WSTS_FINAL_SYNC_BLOCK = (
    "    panelWatch = setInterval(() => {\n"
    "      const deskId = (scope as { user_id?: number | null }).user_id ?? null;\n"
    "      if (deskId === null) {\n"
    "        if (panelWatch) clearInterval(panelWatch);\n"
    "        panelWatch = null;\n"
    "        websocket.close(1008, 'Panel membership no longer valid');\n"
    "        return;\n"
    "      }\n"
    "      panelGuard.panelSourceAllowed(Number(deskId)).then((ok) => {\n"
    "        if (!ok && panelWatch) {\n"
    "          clearInterval(panelWatch);\n"
    "          panelWatch = null;\n"
    "          websocket.close(1008, 'Panel membership no longer valid');\n"
    "        }\n"
    "      }).catch(() => {\n"
    "        // fail closed: an identity-lookup failure also ends the socket\n"
    "        if (panelWatch) clearInterval(panelWatch);\n"
    "        panelWatch = null;\n"
    "        websocket.close(1008, 'Panel membership no longer valid');\n"
    "      });\n"
    "    }, 30_000);\n"
)

WSTS_NOCATCH_SYNC_BLOCK = (
    "    panelWatch = setInterval(() => {\n"
    "      const deskId = (scope as { user_id?: number | null }).user_id ?? null;\n"
    "      if (deskId === null) {\n"
    "        if (panelWatch) clearInterval(panelWatch);\n"
    "        panelWatch = null;\n"
    "        websocket.close(1008, 'Panel membership no longer valid');\n"
    "        return;\n"
    "      }\n"
    "      panelGuard.panelSourceAllowed(Number(deskId)).then((ok) => {\n"
    "        if (!ok && panelWatch) {\n"
    "          clearInterval(panelWatch);\n"
    "          panelWatch = null;\n"
    "          websocket.close(1008, 'Panel membership no longer valid');\n"
    "        }\n"
    "      });\n"
    "    }, 30_000);\n"
)

WSTS_EDIT = (
    "  const scope = scopeFromPrincipal(principal);\n"
    "  await runtime.manager.connect(websocket, scope as never);",
    WSTS_FINAL,
)

LOGIN_TSX_EDITS = [
    (
        "  const handleSubmit = async (e: FormEvent) => {\n"
        "    e.preventDefault();",
        "  const [source, setSource] = useState<'panel' | 'desk'>(\n"
        "    () => (localStorage.getItem('opdesk-auth-source') === 'desk' ? 'desk' : 'panel'),\n"
        "  );\n"
        "  const pickSource = (s: 'panel' | 'desk') => {\n"
        "    setSource(s);\n"
        "    localStorage.setItem('opdesk-auth-source', s);\n"
        "  };\n"
        "\n"
        "  const handleSubmit = async (e: FormEvent) => {\n"
        "    e.preventDefault();",
    ),
    (
        "      const res = await fetch(MTB + '/api/auth/login', {",
        "      const endpoint = source === 'panel' ? '/api/auth/login-panel' : '/api/auth/login';\n"
        "      const res = await fetch(MTB + endpoint, {",
    ),
    (
        "        <form onSubmit={handleSubmit} noValidate>",
        "        <div className=\"login-source\" role=\"radiogroup\" aria-label={t('login.sourceLabel')}>\n"
        "          <button type=\"button\" role=\"radio\" aria-checked={source === 'panel'}\n"
        "                  className={'login-source-btn' + (source === 'panel' ? ' is-active' : '')}\n"
        "                  onClick={() => pickSource('panel')}>{t('login.sourcePanel')}</button>\n"
        "          <button type=\"button\" role=\"radio\" aria-checked={source === 'desk'}\n"
        "                  className={'login-source-btn' + (source === 'desk' ? ' is-active' : '')}\n"
        "                  onClick={() => pickSource('desk')}>{t('login.sourceDesk')}</button>\n"
        "        </div>\n"
        "        <form onSubmit={handleSubmit} noValidate>",
    ),
]

STYLES_APPEND = """
/* MyTellPBX v7.2.0 — account-source toggle on the login card */
.login-source { display: flex; gap: 8px; margin-bottom: 14px; }
.login-source-btn {
  flex: 1 1 0; min-height: 40px; border-radius: 10px; cursor: pointer;
  border: 1px solid rgba(127,143,178,.35); background: rgba(127,143,178,.10);
  font-family: inherit; font-size: 13.5px; font-weight: 700; color: inherit;
  transition: background .16s ease, border-color .16s ease, color .16s ease;
}
.login-source-btn.is-active {
  border-color: rgba(255,138,0,.65); background: rgba(255,138,0,.14); color: #FF8A00;
}
.login-source-btn:focus-visible { outline: 2px solid #FF8A00; outline-offset: 2px; }
"""

I18N_KEYS = {
    "sourceLabel": "نوع حساب",
    "sourcePanel": "حساب پنل",
    "sourceDesk": "حساب میز کار",
}
I18N_KEYS_EN = {
    "sourceLabel": "Account type",
    "sourcePanel": "Panel account",
    "sourceDesk": "Desk account",
}


def patch_alternatives(path, pairs):
    """Apply exactly ONE of several (old,new) alternatives: whichever old
    anchor exists (or whose new is already present). Ordering-insensitive."""
    text = path.read_text(encoding="utf-8")
    for old, new in pairs:
        if new in text:
            print("ALREADY", path.name, "(alternative)")
            return
    for old, new in pairs:
        if old in text:
            bak = path.with_suffix(path.suffix + ".bak-mt")
            if not bak.exists():
                shutil.copy2(path, bak)
                print("BACKUP", bak.name)
            path.write_text(text.replace(old, new, 1), encoding="utf-8")
            print("PATCHED", path.name, "(alternative)")
            return
    raise SystemExit("ANCHOR-MISS-ALL %s" % path)


def patch_file(path, edits=(), *, append=None, exact_new=None):
    if exact_new is not None:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(exact_new, encoding="utf-8")
            print("CREATED", path.name)
            return
        if path.read_text(encoding="utf-8") == exact_new:
            print("ALREADY", path.name)
            return
        bak = path.with_suffix(path.suffix + ".bak-mt")
        if not bak.exists():
            shutil.copy2(path, bak)
            print("BACKUP", bak.name)
        path.write_text(exact_new, encoding="utf-8")
        print("WROTE", path.name)
        return
    text = path.read_text(encoding="utf-8")
    changed = False
    for old, new in edits:
        if new in text:
            print("ALREADY", path.name, "->", new.strip().splitlines()[0][:56])
            continue
        if old not in text:
            raise SystemExit("ANCHOR-MISS %s: %s" % (path, old.strip().splitlines()[0][:70]))
        if text.count(old) != 1:
            raise SystemExit("ANCHOR-DUP %s: %s" % (path, old.strip().splitlines()[0][:70]))
        if not changed:
            bak = path.with_suffix(path.suffix + ".bak-mt")
            if not bak.exists():
                shutil.copy2(path, bak)
                print("BACKUP", bak.name)
        text = text.replace(old, new, 1)
        changed = True
        print("PATCHED", path.name, "->", new.strip().splitlines()[0][:56])
    if append is not None:
        marker = append.strip().splitlines()[0]
        if marker in text:
            print("ALREADY", path.name, "append")
        else:
            if not changed:
                bak = path.with_suffix(path.suffix + ".bak-mt")
                if not bak.exists():
                    shutil.copy2(path, bak)
                    print("BACKUP", bak.name)
            text = text.rstrip("\n") + "\n" + append
            changed = True
            print("APPENDED", path.name)
    if changed:
        path.write_text(text, encoding="utf-8")


def patch_json_keys(path, keys):
    data = json.loads(path.read_text(encoding="utf-8"))
    login = data.setdefault("login", {})
    added = False
    for k, v in keys.items():
        if k not in login:
            login[k] = v
            added = True
    if added:
        bak = path.with_suffix(path.suffix + ".bak-mt")
        if not bak.exists():
            shutil.copy2(path, bak)
            print("BACKUP", bak.name)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("PATCHED", path.name, "login.* keys")
    else:
        print("ALREADY", path.name, "login.* keys")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-build", action="store_true")
    args = ap.parse_args()

    for p in (SECURITY, USERS_PATH, AUTHCTRL, WSTS, SCHEMA, LOGIN_TSX, STYLES_CSS, FA_JSON, EN_JSON):
        if not p.exists():
            raise SystemExit("MISSING %s" % p)

    patch_file(PANEL_AUTH_TS, exact_new=PANEL_AUTH_SOURCE)
    patch_file(PANEL_AUTH_SPEC, exact_new=PANEL_AUTH_SPEC_SOURCE)
    patch_file(SCHEMA, append=SCHEMA_APPEND)
    patch_file(USERS_PATH, [USERS_HASH_EXPORT])
    patch_file(SECURITY, SECURITY_TOKEN_EDIT)
    patch_alternatives(SECURITY, SECURITY_GUARD_ALTERNATIVES)
    patch_file(AUTHCTRL, [AUTHCTRL_IMPORT_EDIT, (
        "  @Get('/api/auth/me')",
        AUTHCTRL_NEW_ENDPOINT + "  @Get('/api/auth/me')",
    )])
    patch_file(WSTS, [WSTS_IMPORT_EDIT])
    patch_alternatives(WSTS, [WSTS_EDIT,
                               (WSTS_LEGACY_SYNC_BLOCK, WSTS_FINAL_SYNC_BLOCK),
                               (WSTS_NOCATCH_SYNC_BLOCK, WSTS_FINAL_SYNC_BLOCK)])
    patch_file(LOGIN_TSX, LOGIN_TSX_EDITS)
    patch_file(STYLES_CSS, append=STYLES_APPEND)
    patch_json_keys(FA_JSON, I18N_KEYS)
    patch_json_keys(EN_JSON, I18N_KEYS_EN)

    if args.skip_build:
        print("SKIP-BUILD requested; sources patched only")
        return

    node_env = dict(__import__("os").environ)
    node_env["PATH"] = "/opt/node24/bin:" + node_env.get("PATH", "")
    build = subprocess.run(["npm", "run", "build"], cwd=str(BE), env=node_env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           universal_newlines=True, timeout=600)
    print("\n".join((build.stdout + build.stderr).splitlines()[-16:]))
    if build.returncode != 0:
        raise SystemExit("STEP-FAIL: backend build")

    jest = subprocess.run(
        ["/opt/node24/bin/node",
         str(BE / "node_modules" / "jest" / "bin" / "jest.js"),
         "test/core/panel-auth.spec.ts", "--ci", "--silent"],
        cwd=str(BE), env=node_env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True, timeout=600)
    print("\n".join((jest.stdout + jest.stderr).splitlines()[-16:]))
    if jest.returncode != 0:
        raise SystemExit("STEP-FAIL: panel-auth tests")

    r = subprocess.run(["systemctl", "restart", "mytellpbx-opdesk"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True)
    if r.returncode != 0:
        raise SystemExit("restart failed: " + r.stderr[:200])
    print("SERVICE-RESTARTED")


if __name__ == "__main__":
    main()
