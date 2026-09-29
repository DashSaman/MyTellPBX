<?php
/* vim: set expandtab tabstop=4 softtabstop=4 shiftwidth=4:
  Codificación: UTF-8
  +----------------------------------------------------------------------+
  | MyTellPBX theme for Issabel 5 (based on the Issabel tenant theme)    |
  | https://github.com/DashSaman/MyTellPBX                               |
  +----------------------------------------------------------------------+
  | The contents of this file are subject to the General Public License  |
  | (GPL) Version 2 (the "License"); you may not use this file except in |
  | compliance with the License. You may obtain a copy of the License at |
  | http://www.opensource.org/licenses/gpl-license.php                   |
  +----------------------------------------------------------------------+
  | Tabler icons used under the MIT License (https://tabler.io/icons)    |
  +----------------------------------------------------------------------+
*/
function themeSetup(&$smarty, $selectedMenu, $pdbACL, $pACL, $idUser)
{
    $lang = get_language();
    $arrMainMenu = $smarty->get_template_vars('arrMainMenu');

    foreach($arrMainMenu as $idMenu=>$arrMenuItem) {
        $arrMainMenu[$idMenu]['icon'] = setIcon($idMenu);
    }

    $smarty->assign('arrMainMenu', $arrMainMenu);
    $smarty->assign("LANG", $lang);
    $extension = $pACL->getUserExtension($_SESSION['issabel_user']);
    $smarty->assign(array(
        "ABOUT_ISSABEL2"            =>  'About MyTellPBX',
        "HELP"                      =>  _tr('HELP'),
        "USER_LOGIN"                =>  $_SESSION['issabel_user'],
        "USER_ID"                   =>  $idUser,
        "EXTENSION"                 =>  $extension,
        "CHANGE_PASSWORD"           =>  'Change MyTellPBX Password',
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
        'LBL_NO_STICKY'             =>  _tr('No description'),
    ));
}
function setIcon($idMenu){
    switch ($idMenu) {
        case 'manager': return 'ti ti-settings';
        case 'system': return 'ti ti-device-desktop-analytics';
        case 'email_admin': return 'ti ti-mail';
        case 'security': return 'ti ti-shield-lock';
        case 'pbxconfig': return 'ti ti-phone';
        case 'fax': return 'ti ti-printer';
        case 'reports': return 'ti ti-chart-bar';
        case 'im': return 'ti ti-messages';
        case 'agenda': return 'ti ti-address-book';
        case 'my_extension': return 'ti ti-device-mobile';
        case 'addons': return 'ti ti-box';
        case 'extras': return 'ti ti-puzzle';

        default: return 'ti ti-point';
    }
 }

 function setBreadcrumb($arrMainMenu,$currentMenu){

      foreach ($arrMainMenu as $key => $value) {
            $breadcrumb = array();
            array_push($breadcrumb, $value["Name"]);
            if($key == $currentMenu)
               return $breadcrumb;

            foreach ($arrMainMenu[$key]["children"] as $akey ) {
                 if(count($breadcrumb)>1)
                    array_pop($breadcrumb);

                array_push($breadcrumb, $akey["Name"]);
                 if($akey["id"] == $currentMenu)
                    return $breadcrumb;

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
