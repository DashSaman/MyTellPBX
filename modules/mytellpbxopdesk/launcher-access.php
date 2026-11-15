<?php
/** Native panel authorization only. No token minting or shared credentials. */
function mytellDeskLauncherStatus($username, $lookup)
{
    if (!is_string($username) || $username === '') return 401;
    try {
        return call_user_func($lookup, $username) === true ? 303 : 403;
    } catch (Exception $error) {
        return 503;
    } catch (Throwable $error) {
        return 503;
    }
}

function mytellDeskOpenAcl($path = '/var/www/db/acl.db')
{
    if (!is_file($path) || !is_readable($path)) throw new RuntimeException('Panel authorization unavailable');
    // PDO's default SQLite flags may create an empty DB. A missing/replaced ACL
    // must fail closed instead; PHP7.4 exposes these read-only open flags.
    if (!defined('PDO::SQLITE_ATTR_OPEN_FLAGS') || !defined('PDO::SQLITE_OPEN_READONLY')) {
        throw new RuntimeException('Read-only panel authorization unavailable');
    }
    return new PDO('sqlite:' . $path, null, null, array(
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_TIMEOUT => 2,
        PDO::SQLITE_ATTR_OPEN_FLAGS => PDO::SQLITE_OPEN_READONLY,
    ));
}

function mytellDeskAclAllows($acl, $username)
{
    $statement = $acl->prepare('SELECT COUNT(*) FROM acl_membership M JOIN acl_user U ON U.id = M.id_user WHERE U.name = ? AND M.id_group = 1');
    $statement->execute(array($username));
    return (int)$statement->fetchColumn() > 0;
}
