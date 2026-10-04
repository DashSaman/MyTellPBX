<?php
/* vim: set expandtab tabstop=4 softtabstop=4 shiftwidth=4:
  Codificación: UTF-8
  +----------------------------------------------------------------------+
  | MyTel theme for Issabel 5 - themesetup hook                          |
  | Presentation-layer only: menu icons, breadcrumb, notifications,      |
  | layout direction. Based on the stock tenant themeSetup contract.     |
  +----------------------------------------------------------------------+
*/
function themeSetup(&$smarty, $selectedMenu, $pdbACL, $pACL, $idUser)
{
    $lang = get_language();

    $arrMainMenu = $smarty->get_template_vars('arrMainMenu');
    if (is_array($arrMainMenu)) {
        foreach($arrMainMenu as $idMenu=>$arrMenuItem) {
            $arrMainMenu[$idMenu]['icon'] = setIcon($idMenu);
        }
    }

    $idMainMenuSelected = $smarty->get_template_vars('idMainMenuSelected');
    $MAX_ITEMS_VISIBLES = 12;

    if (is_array($arrMainMenu) && count($arrMainMenu) > $MAX_ITEMS_VISIBLES) {
        $tempMenulist = array();
        $idxMainMenu = NULL;
        foreach ($arrMainMenu as $key => $value) {
            if ($key == $idMainMenuSelected) $idxMainMenu = count($tempMenulist);
            $tempMenulist[] = array($key, $value);
        }
        if (!is_null($idxMainMenu) && $idxMainMenu >= $MAX_ITEMS_VISIBLES) {
            $menuitem = array_splice($tempMenulist, $idxMainMenu, 1);
            array_splice($tempMenulist, $MAX_ITEMS_VISIBLES - 1, 0, $menuitem);
            $arrMainMenu = array();
            foreach ($tempMenulist as $menuitem) $arrMainMenu[$menuitem[0]] = $menuitem[1];
        }
        unset($tempMenulist);
    }

    $smarty->assign('arrMainMenu', $arrMainMenu);
    $smarty->assign("LANG", $lang);
    $smarty->assign("THEME_DIR", ($lang == 'fa' || $lang == 'pe') ? 'rtl' : 'ltr');
    $smarty->assign("BRAND_NAME", 'مای‌تل');
    $smarty->assign("BRAND_NAME_LATIN", 'MyTel');
    $smarty->assign("BRAND_TAGLINE", 'سامانه مدیریت مرکز تماس');
    $extension = $pACL->getUserExtension($_SESSION['issabel_user']);
    $smarty->assign(array(
        "ABOUT_ISSABEL2"            =>  _tr('About Issabel'),
        "HELP"                      =>  _tr('HELP'),
        "USER_LOGIN"                =>  $_SESSION['issabel_user'],
        "USER_ID"                   =>  $idUser,
        "EXTENSION"                 =>  $extension,
        "CHANGE_PASSWORD"           =>  _tr("Change Issabel Password"),
        "MODULES_SEARCH"            =>  _tr("Search modules"),
        "ADD_BOOKMARK"              =>  _tr("Add Bookmark"),
        "REMOVE_BOOKMARK"           =>  _tr("Remove Bookmark"),
        "ADDING_BOOKMARK"           =>  _tr("Adding Bookmark"),
        "REMOVING_BOOKMARK"         =>  _tr("Removing Bookmark"),
        "HIDING_IZQTAB"             =>  _tr("Hiding left panel"),
        "SHOWING_IZQTAB"            =>  _tr("Loading left panel"),
        "HIDE_IZQTAB"               =>  _tr("Hide left panel"),
        "SHOW_IZQTAB"               =>  _tr("Load left panel"),

        'viewMenuTab'               =>  getStatusNeoTabToggle($pdbACL, $idUser),
        'MENU_COLOR'                =>  getMenuColorByMenu($pdbACL, $idUser),
        'IMG_BOOKMARKS'             =>  menuIsBookmark($pdbACL, $idUser, $selectedMenu) ? 'bookmarkon.png' : 'bookmark.png',
        'SHORTCUT'                  =>  loadShortcut($pdbACL, $idUser, $smarty),
        'BREADCRUMB'                =>  setBreadcrumb($arrMainMenu,$selectedMenu),
        'NOTIFICATIONS'             =>  loadSystemNotifications($pdbACL, $idUser),
    ));
}
function setIcon($idMenu){
    switch ($idMenu) {
        case 'manager': return 'fa fa-cog';
        case 'system': return 'fa fa-laptop';
        case 'email_admin': return 'fa fa-envelope';
        case 'security': return 'fa fa-lock';
        case 'pbxconfig': return 'fa fa-phone';
        case 'fax': return 'fa fa-print';
        case 'reports': return 'fa fa-bar-chart-o';
        case 'im': return 'fa fa-comments';
        case 'agenda': return 'fa fa-book';
        case 'my_extension': return 'fa fa-fax';
        case 'addons': return 'fa fa-cubes';
        case 'extras': return 'fa fa-plus';
        default: return 'fa fa-caret-left';
    }
 }
function setBreadcrumb($arrMainMenu,$currentMenu){
      if (!is_array($arrMainMenu)) return array();
      foreach ($arrMainMenu as $key => $value) {
            $breadcrumb = array();
            array_push($breadcrumb, $value["Name"]);
            if($key == $currentMenu) return $breadcrumb;
            foreach ($arrMainMenu[$key]["children"] as $akey ) {
                 if(count($breadcrumb)>1) array_pop($breadcrumb);
                 array_push($breadcrumb, $akey["Name"]);
                 if($akey["id"] == $currentMenu) return $breadcrumb;
                 if($akey["HasChild"]) {
                   foreach ($akey["children"] as $bkey => $bvalue) {
                       if($bkey == $currentMenu){
                           array_push($breadcrumb, $bvalue["Name"]);
                           return $breadcrumb;
                       }
                   }
                 }
            }
      }
      return array();
}
function loadSystemNotifications($pdbACL, $idUser)
{
    require_once 'libs/paloSantoNotification.class.php';
    $pNot = new paloNotification($pdbACL);
    $a = array(
        'LBL_NOTIFICATION_SYSTEM'   =>  _tr('System'),
        'LBL_NOTIFICATION_USER'     =>  _tr('User'),
        'NOTIFICATIONS_PUBLIC'      =>  $pNot->listPublicNotifications(3),
        'NOTIFICATIONS_PRIVATE'     =>  $pNot->listUserNotifications($idUser, 3),
        'TXT_NO_NOTIFICATIONS'      =>  _tr('No notifications'),
    );
    return $a;
}
?>
