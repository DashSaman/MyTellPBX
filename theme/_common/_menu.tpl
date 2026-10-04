<input type="hidden" id="userMenuColor" value="{$MENU_COLOR}" />
<input type="hidden" id="toolTip_addBookmark" value="{$ADD_BOOKMARK}" />
<input type="hidden" id="toolTip_removeBookmark" value="{$REMOVE_BOOKMARK}" />
<input type="hidden" id="toolTip_addingBookmark" value="{$ADDING_BOOKMARK}" />
<input type="hidden" id="toolTip_removingBookmark" value="{$REMOVING_BOOKMARK}" />
<input type="hidden" id="toolTip_hideTab" value="{$HIDE_IZQTAB}" />
<input type="hidden" id="toolTip_showTab" value="{$SHOW_IZQTAB}" />
<input type="hidden" id="toolTip_hidingTab" value="{$HIDING_IZQTAB}" />
<input type="hidden" id="toolTip_showingTab" value="{$SHOWING_IZQTAB}" />
<input type="hidden" id="amount_char_label" value="{$AMOUNT_CHARACTERS}" />
<input type="hidden" id="save_note_label" value="{$MSG_SAVE_NOTE}" />
<input type="hidden" id="get_note_label" value="{$MSG_GET_NOTE}" />
<input type="hidden" id="issabel_theme_name" value="{$THEMENAME}" />
<input type="hidden" id="lbl_no_description" value="{$LBL_NO_STICKY}" />

<!-- sidebar -->
<div class="sidebar-menu mt-sidebar" id="mt-sidebar">
    <header class="logo-env mt-logo-env">
        <div class="logo">
            <a href="index.php" class="mt-brand">
                <img src="{$WEBPATH}themes/{$THEMENAME}/images/mytel-emblem.svg" alt="{$BRAND_NAME}" class="mt-brand-emblem" />
                <span class="mt-brand-text">
                    <b class="mt-brand-name">{$BRAND_NAME}</b>
                    <small class="mt-brand-sub">{$BRAND_TAGLINE}</small>
                </span>
            </a>
        </div>
        <div class="sidebar-collapse">
            <a href="#" class="sidebar-collapse-icon without-animation" title="{$HIDE_IZQTAB}">
                <i class="fa fa-bars"></i>
            </a>
        </div>
        <div class="sidebar-mobile-menu visible-xs">
            <a href="#" class="without-animation">
                <i class="fa fa-bars"></i>
            </a>
        </div>
    </header>

    <ul id="main-menu" class="">
        <li id="search" class="mt-menu-search">
            <form method="get" action="" onsubmit="return false;">
                <input type="text" id="search_module_issabel" name="search_module_issabel" class="search-input" placeholder="{$MODULES_SEARCH}" autocomplete="off"/>
                <button type="submit" tabindex="-1">
                    <i class="fa fa-search"></i>
                </button>
            </form>
        </li>
        {foreach from=$arrMainMenu key=idMenu item=menu name=menuMain}
            {if $idMenu eq $idMainMenuSelected}
                <li class="active opened active">
            {else}
                <li>
            {/if}
                    <a href="index.php?menu={$idMenu}">
                         <i class="{$menu.icon}"></i>
                        <span>{$menu.Name}</span>
                    </a>
                    <ul>
                        {foreach from=$menu.children key=idSubMenu item=subMenu}
                            {if $idSubMenu eq $idSubMenuSelected}
                                <li class="active opened active">
                            {else}
                                <li>
                            {/if}
                            {if $subMenu.Type eq "popup"}
                                <a href="{$subMenu.Link}" target="{$idSubMenu}">
                                    <span>{$subMenu.Name}</span>
                                </a>
                            {else}
                                <a href="index.php?menu={$idSubMenu}">
                                    <span>{$subMenu.Name}</span>
                                </a>
                            {/if}
                            {if $subMenu.children}
                                <ul>
                                    {foreach from=$subMenu.children key=idSubMenu2 item=subMenu2}
                                        <li>
                                            {if $subMenu2.Type eq "popup"}
                                                <a href="{$subMenu2.Link}" target="{$idSubMenu2}">
                                                    <span>{$subMenu2.Name}</span>
                                                </a>
                                            {else}
                                                <a href="index.php?menu={$idSubMenu2}">
                                                    <span>{$subMenu2.Name}</span>
                                                </a>
                                            {/if}
                                        </li>
                                    {/foreach}
                                </ul>
                            {/if}
                        </li>
                        {/foreach}
                    </ul>
                </li>
        {/foreach}

        {$SHORTCUT}

    </ul>
</div>
<!-- /sidebar -->

<div class="main-content mt-main-content">

<div class="mt-topbar">
    <div class="mt-topbar-right">
        <button type="button" class="mt-topbar-burger" id="mt-burger" aria-label="menu">
            <i class="fa fa-bars"></i>
        </button>
    </div>

    <!-- Profile Info and Notifications -->
    <div class="mt-topbar-left">
        <ul class="user-info mt-user-info">
            <li class="profile-info dropdown">
                <a href="#" class="dropdown-toggle mt-user-toggle" data-toggle="dropdown">
                    <span class="mt-avatar"><i class="fa fa-user"></i></span>
                    <span class="mt-user-name">{$USER_LOGIN}</span>
                    <i class="fa fa-angle-down mt-caret"></i>
                </a>
                <ul class="dropdown-menu mt-user-menu">
                    <li class="caret"></li>
                    <li class="dropdown">
                        <a href="#" class="setadminpassword">
                            <i class="fa fa-user"></i>
                            {$CHANGE_PASSWORD}
                        </a>
                    </li>
                    <li class="dropdown">
                        <a href="index.php?logout=yes">
                            <i class="fa fa-sign-out"></i>
                            {$LOGOUT}
                        </a>
                    </li>
                </ul>
            </li>
        </ul>

        <ul class="list-inline links-list pull-right neo-topbar-notification mt-topbar-links">
        <li id="header_notification_bar" class="profile-info dropdown pull-right notifications">
            <a data-toggle="dropdown" class="" href="#">
                <i id='notibell' class="fa fa-bell-o {$ANIMATE_NOTIFICATION}"></i>
            </a>
            <ul class="dropdown-menu mt-noti-menu">
                <li class="caret"></li>
                <li><p class="mt-noti-head">{$NOTIFICATIONS.LBL_NOTIFICATION_SYSTEM}</p></li>
                <li>
                    <ul class="mt-noti-list">
                        {foreach from=$NOTIFICATIONS.NOTIFICATIONS_PUBLIC item=NOTI}
                            <li id='notiitem{$NOTI.id}' class="{if $NOTI.level == "info"}notification-info{elseif $NOTI.level == "warning"}notification-warning{elseif $NOTI.level == "error"}notification-danger{/if}">
                                <a href="#" onclick='readNoti("{$NOTI.id}")'><i class="{if $NOTI.level == "info"}fa fa-info{elseif $NOTI.level == "warning"}fa fa-warning{elseif $NOTI.level == "error"}fa fa-ban{/if}"></i>{$NOTI.content}</a>
                            </li>
                        {foreachelse}
                            <li><p class="mt-noti-empty">{$NOTIFICATIONS.TXT_NO_NOTIFICATIONS}</p></li>
                        {/foreach}
                    </ul>
                </li>
                <li><p class="mt-noti-head">{$NOTIFICATIONS.LBL_NOTIFICATION_USER}</p></li>
                <li>
                    <ul class="mt-noti-list">
                        {foreach from=$NOTIFICATIONS.NOTIFICATIONS_PRIVATE item=NOTI}
                            <li class="{if $NOTI.level == "info"}notification-info{elseif $NOTI.level == "warning"}notification-warning{elseif $NOTI.level == "error"}notification-danger{/if}">
                                <a href="#"><i class="{if $NOTI.level == "info"}fa fa-info{elseif $NOTI.level == "warning"}fa fa-warning{elseif $NOTI.level == "error"}fa fa-ban{/if}"></i>{$NOTI.content}</a>
                            </li>
                        {foreachelse}
                            <li><p class="mt-noti-empty">{$NOTIFICATIONS.TXT_NO_NOTIFICATIONS}</p></li>
                        {/foreach}
                    </ul>
                </li>
            </ul>
        </li>
{if $ISSABEL_PANELS}
        <li id="header_open_sidebar">
            <a href="#" data-toggle="chat" data-collapse-sidebar="1"><i class="fa fa-th-list"></i></a>
        </li>
{/if}
        </ul>
    </div>
</div>

<!-- Breadcrumb -->
<ol class="breadcrumb bc-2 mt-breadcrumb">

    {foreach from=$BREADCRUMB item=value name=menu}
        {if $smarty.foreach.menu.first}
             <li>
                <a href="index.php"> <i class="fa fa-home"></i></a>
                <a href="#"> {$value}</a>
             </li>
        {elseif $smarty.foreach.menu.last}
            <li class="active"><strong>{$value}</strong></li>
        {else}
            <li><a href="#">{$value}</a></li>
        {/if}
   {/foreach}
   <li id="tenant-sticky" class="dropdown mt-sticky-toggle">
       <a id="togglestickynote1" href="#">
           <i class="fa fa-file-text-o"></i>
       </a>
   </li>
</ol>

<!-- module content -->
<div id="neo-contentbox">
    <div id="neo-contentbox-maincolumn">
        <input type="hidden" id="issabel_framework_module_id" value="{if empty($idSubMenu2Selected)}{$idSubMenuSelected}{else}{$idSubMenu2Selected}{/if}" />
        <input type="hidden" id="issabel_framework_webCommon" value="{$WEBCOMMON}" />
        <div class="neo-module-content mt-module-content">
