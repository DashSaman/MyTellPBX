#!/usr/bin/env python3
"""MyTellPBX v7.3.0 — theme toggle for the desk (MyTellDesk).

Surfaces the existing theme engine (localStorage 'opdesk:theme' +
<html data-theme>, complete dark/light palettes in styles/variables.css):
  1) new src/components/ThemeToggle.tsx — compact icon button (Sun/Moon).
     Controlled when App passes theme/onToggle; otherwise self-managing
     against the same storage key + document attribute (pre-login screen,
     where App is not mounted — same single source of truth).
  2) App.tsx — header toggle beside the profile button (physical right
     cluster on every route), wired to the existing theme/selectTheme.
  3) Login.tsx — page-level toggle at the physical top-right (16px),
     self-managing variant.
  4) styles/index.css — toggle styles + light-mode AA fix for the
     account-source selector (was 2.10:1 orange-on-white).
  5) rebuild with --base=/MytellDesk/

Usage (root):  python3 patch-desk-theme.py
Idempotent (marker/anchor based); .bak-mt backups; nonzero on drift.
"""
import pathlib
import shutil
import subprocess
import sys

FE = pathlib.Path("/opt/opdesk/frontend")
SRC = FE / "src"

TOGGLE_TS = """/**
 * MyTellPBX v7.3.0 — compact theme toggle (Sun/Moon).
 * Controlled when App supplies props; self-managing otherwise (login
 * screen) against the same 'opdesk:theme' storage + <html data-theme>
 * the app engine uses — one source of truth, no divergence.
 */
import { useEffect, useState } from 'react';
import { Sun, Moon } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const THEME_KEY = 'opdesk:theme';

type Props = {
  theme?: 'dark' | 'light';
  onToggle?: (next: 'dark' | 'light') => void;
  variant?: 'header' | 'floating';
};

function currentTheme(): 'dark' | 'light' {
  try {
    const v = localStorage.getItem(THEME_KEY);
    if (v === 'dark' || v === 'light') return v;
  } catch { /* ignore */ }
  if (typeof window !== 'undefined' && window.matchMedia
      && window.matchMedia('(prefers-color-scheme: light)').matches) return 'light';
  return 'dark';
}

export function ThemeToggle({ theme, onToggle, variant = 'header' }: Props) {
  const { t } = useTranslation();
  const [self, setSelf] = useState<'dark' | 'light'>(() =>
    typeof document !== 'undefined'
      ? ((document.documentElement.dataset.theme as 'dark' | 'light') || currentTheme())
      : 'dark');
  useEffect(() => {
    if (theme) setSelf(theme);
  }, [theme]);
  const active = theme ?? self;
  const dark = active === 'dark';
  const click = () => {
    const next: 'dark' | 'light' = dark ? 'light' : 'dark';
    if (onToggle) {
      onToggle(next);
    } else {
      document.documentElement.dataset.theme = next;
      try { localStorage.setItem(THEME_KEY, next); } catch { /* ignore */ }
      setSelf(next);
    }
  };
  return (
    <button
      type="button"
      className={'theme-toggle' + (variant === 'floating' ? ' theme-toggle-floating' : '')}
      onClick={click}
      aria-pressed={dark}
      aria-label={dark ? t('header.switchLight', 'تغییر به حالت روشن') : t('header.switchDark', 'تغییر به حالت تاریک')}
      title={dark ? t('header.switchLight', 'تغییر به حالت روشن') : t('header.switchDark', 'تغییر به حالت تاریک')}
    >
      {dark ? <Sun size={16} aria-hidden="true" /> : <Moon size={16} aria-hidden="true" />}
    </button>
  );
}
"""

CSS_APPEND = """
/* MyTellPBX v7.3.0 — theme toggle (header + login floating) */
.theme-toggle {
  display: inline-flex; align-items: center; justify-content: center;
  width: 36px; height: 36px; border-radius: 9px; cursor: pointer;
  border: 1px solid var(--border, rgba(127,143,178,.35));
  background: transparent; color: var(--text-muted, #8fa0ba);
  transition: color .12s ease, background .12s ease, border-color .12s ease;
}
.theme-toggle:hover { color: var(--accent, #FF8A00); border-color: var(--accent, #FF8A00); }
.theme-toggle:focus-visible { outline: 2px solid #B8B9FF; outline-offset: 3px; }
.theme-toggle-floating { position: fixed; top: 16px; right: 16px; z-index: 60; }
@media (pointer: coarse) { .theme-toggle { width: 44px; height: 44px; } }

/* light-mode AA fix for the account-source selector (was ~2.10:1) */
:root[data-theme="light"] .login-source-btn.is-active {
  color: #9C4D00;
  border-color: rgba(230,122,0,.65);
  background: rgba(255,138,0,.16);
}
"""

I18N = {
    "fa": {"switchLight": "تغییر به حالت روشن", "switchDark": "تغییر به حالت تاریک"},
    "en": {"switchLight": "Switch to light mode", "switchDark": "Switch to dark mode"},
}


def patch(path, edits=(), *, append=None, exact_new=None):
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
            print("ALREADY", path.name, "->", new.strip().splitlines()[0][:50])
            continue
        if old not in text:
            raise SystemExit("ANCHOR-MISS %s: %s" % (path, old.strip().splitlines()[0][:60]))
        if not changed:
            bak = path.with_suffix(path.suffix + ".bak-mt")
            if not bak.exists():
                shutil.copy2(path, bak)
                print("BACKUP", bak.name)
        text = text.replace(old, new, 1)
        changed = True
        print("PATCHED", path.name, "->", new.strip().splitlines()[0][:50])
    if append is not None:
        mk = append.strip().splitlines()[0]
        if mk in text:
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


def patch_i18n(lang, keys):
    import json
    p = SRC / ("i18n/locales/%s/translation.json" % lang)
    d = json.loads(p.read_text(encoding="utf-8"))
    head = d.setdefault("header", {})
    added = False
    for k, v in keys.items():
        if k not in head:
            head[k] = v
            added = True
    if added:
        bak = p.with_suffix(p.suffix + ".bak-mt")
        if not bak.exists():
            shutil.copy2(p, bak)
            print("BACKUP", p.name)
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("PATCHED", p.name, "header.switch*")
    else:
        print("ALREADY", p.name, "header.switch*")


APP_EDITS = [
    # import the shared toggle next to the existing profile imports
    (
        "import type { LucideIcon } from 'lucide-react';",
        "import type { LucideIcon } from 'lucide-react';\nimport { ThemeToggle } from './components/ThemeToggle';",
    ),
    # header: place the toggle immediately BEFORE the profile group (right cluster)
    (
        "          {/* Profile menu: identity + preferences (appearance, language) + sign out */}\n"
        "          <div ref={profileMenuRef} className=\"header-profile\">",
        "          {/* MyTellPBX v7.3.0: theme toggle beside the profile button */}\n"
        "          <ThemeToggle theme={theme} onToggle={selectTheme} />\n"
        "\n"
        "          {/* Profile menu: identity + preferences (appearance, language) + sign out */}\n"
        "          <div ref={profileMenuRef} className=\"header-profile\">",
    ),
]

LOGIN_EDITS = [
    (
        "import { setToken, setUser } from '../auth';",
        "import { setToken, setUser } from '../auth';\nimport { ThemeToggle } from './ThemeToggle';",
    ),
    (
        "  return (\n    <div className=\"login-page\">",
        "  return (\n    <div className=\"login-page\">\n      <ThemeToggle variant=\"floating\" />",
    ),
]


def main():
    for p in (SRC / "App.tsx", SRC / "components/Login.tsx", SRC / "styles/index.css"):
        if not p.exists():
            raise SystemExit("MISSING %s" % p)
    patch(SRC / "components/ThemeToggle.tsx", exact_new=TOGGLE_TS)
    patch(SRC / "App.tsx", APP_EDITS)
    patch(SRC / "components/Login.tsx", LOGIN_EDITS)
    patch(SRC / "styles/index.css", append=CSS_APPEND)
    for lang, keys in I18N.items():
        patch_i18n(lang, keys)

    node_env = dict(__import__("os").environ)
    node_env["PATH"] = "/opt/node24/bin:" + node_env.get("PATH", "")
    b = subprocess.run(["npx", "vite", "build", "--base=/MytellDesk/"], cwd=str(FE), env=node_env,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True, timeout=600)
    print("\n".join((b.stdout + b.stderr).splitlines()[-8:]))
    sys.exit(0 if b.returncode == 0 else 1)


if __name__ == "__main__":
    main()
