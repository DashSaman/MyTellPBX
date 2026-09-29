{literal}
<script type='text/javascript'>
var themeName='mytellpbx'; //theme name
$(document).ready(function(){
    LblRegister = '{/literal}{$Register}{literal}';
    $("#export_button").hover(
      function () {
          $(this).addClass("exportBorder");
      },
      function () {
          $(this).removeClass("exportBorder");
          $(this).attr("aria-expanded","false");
          $(this).removeClass("exportBackground");
          $(".letranodec").css("color","#444444");
          $("#subMenuExport").addClass("neo-display-none");
      }
    );
    $("#neo-table-button-download-right").click(
      function () {
          if($(this).attr("aria-expanded") == "false"){
          var exportPosition = $('#export_button').position();
          var top = exportPosition.top + 41;
          var left = exportPosition.left - 3;
          $("#subMenuExport").css('top',top+"px");
          $("#subMenuExport").css('left',left+"px");
          $(this).attr("aria-expanded","true");
          $(this).addClass("exportBackground");
          $(".letranodec").css("color","#FFFFFF");
          $("#subMenuExport").removeClass("neo-display-none");
          }
          else{
          $(".letranodec").css("color","#444444");
          $("#subMenuExport").addClass("neo-display-none");
          $(this).removeClass("exportBackground");
          $(this).attr("aria-expanded","false");
          }
      }
    );
    $("#subMenuExport").hover(
      function () {
        $(this).removeClass("neo-display-none");
        $(".letranodec").css("color","#FFFFFF");
        $("#export_button").attr("aria-expanded","true");
        $("#export_button").addClass("exportBackground");
      },
      function () {
        $(this).addClass("neo-display-none");
        $(".letranodec").css("color","#444444");
        $("#export_button").removeClass("exportBackground");
        $("#export_button").attr("aria-expanded","false");
      }
    );
   $('#header_open_sidebar, a.chat-close').click(function (e) {
      $('div.page-container').toggleClass('chat-visible');
      toggle_sidebar_menu(true);
      e.stopPropagation();
   });
});
</script>
{/literal}

<aside class="navbar navbar-vertical navbar-expand-lg" id="navbar-vertical">
    <div class="container-fluid">
        <h1 class="navbar-brand navbar-brand-autodark mb-0">
            <a href="index.php" style="display:flex;align-items:center;gap:.5rem;text-decoration:none;">
                <img src="{$WEBPATH}themes/{$THEMENAME}/images/logo.svg" width="32" height="32" alt="MyTellPBX" />
                <span style="font-size:1.05rem;">MyTellPBX</span>
            </a>
        </h1>
        <div class="nav-item d-none d-lg-flex flex-column w-100">
            <form method="get" action="" role="search" class="my-2">
                <input type="text" id="search_module_issabel" name="search_module_issabel" class="form-control form-control-sm" placeholder="{$MODULES_SEARCH}" autocomplete="off"/>
            </form>
        </div>
        <div class="d-flex d-lg-none w-100 my-1 justify-content-end">
            <button class="btn btn-outline-secondary btn-sm" type="button" id="sidebar-collapse-mobile" aria-label="Menu">
                <i class="ti ti-menu-2"></i>
            </button>
        </div>
        <div class="collapse navbar-collapse" id="sidebar-menu">
            <div class="d-lg-none my-2">
                <input type="text" id="search_module_issabel_mobile" class="form-control form-control-sm" placeholder="{$MODULES_SEARCH}" autocomplete="off"/>
            </div>
            <ul class="navbar-nav pt-lg-3" id="main-menu">
                <!--recorremos el arreglo del menu nivel primario-->
                {foreach from=$arrMainMenu key=idMenu item=menu name=menuMain}
                    {if $idMenu eq $idMainMenuSelected}
                    <li class="nav-item dropdown active opened">
                    {else}
                    <li class="nav-item dropdown">
                    {/if}
                        <a class="nav-link dropdown-toggle{if $idMenu eq $idMainMenuSelected} show{/if}" href="#navbar-menu-{$idMenu}"
                           role="button" data-menu-group="navbar-menu-{$idMenu}"
                           aria-expanded="{if $idMenu eq $idMainMenuSelected}true{else}false{/if}">
                            <span class="nav-link-icon"><i class="{$menu.icon}"></i></span>
                            <span class="nav-link-title">{$menu.Name}</span>
                        </a>
                        <div class="dropdown-menu{if $idMenu eq $idMainMenuSelected} show{/if}" id="navbar-menu-{$idMenu}">
                            <!--recorremos el arreglo del menu nivel secundario-->
                            {foreach from=$menu.children key=idSubMenu item=subMenu}
                                {if $subMenu.Type eq "popup"}
                                <a class="dropdown-item{if $idSubMenu eq $idSubMenuSelected} active{/if}" href="{$subMenu.Link}" target="{$idSubMenu}">
                                    {$subMenu.Name}
                                </a>
                                {else}
                                <a class="dropdown-item{if $idSubMenu eq $idSubMenuSelected} active{/if}" href="index.php?menu={$idSubMenu}">
                                    {$subMenu.Name}
                                </a>
                                {/if}
                                {if $subMenu.children}
                                    <!--menu de tercer nivel-->
                                    {foreach from=$subMenu.children key=idSubMenu2 item=subMenu2}
                                        {if $subMenu2.Type eq "popup"}
                                        <a class="dropdown-item sub-item{if $idSubMenu2 eq $idSubMenu2Selected} active{/if}" href="{$subMenu2.Link}" target="{$idSubMenu2}">
                                            {$subMenu2.Name}
                                        </a>
                                        {else}
                                        <a class="dropdown-item sub-item{if $idSubMenu2 eq $idSubMenu2Selected} active{/if}" href="index.php?menu={$idSubMenu2}">
                                            {$subMenu2.Name}
                                        </a>
                                        {/if}
                                    {/foreach}
                                {/if}
                            {/foreach}
                        </div>
                    </li>
                {/foreach}

                {$SHORTCUT}
            </ul>
        </div>
    </div>
</aside>

<!-- inicio del head principal-->
<div class="page-wrapper">
<header class="page-header d-print-none">
    <div class="container-fluid">
        <div class="row align-items-center g-2">
            <div class="col">
                <!-- Breadcrumb -->
                <ol class="breadcrumb mytell-breadcrumb mb-0">
                    {foreach from=$BREADCRUMB item=value name=menu}
                        {if $smarty.foreach.menu.last}
                            <li class="breadcrumb-item active"><strong>{$value}</strong></li>
                        {else}
                            <li class="breadcrumb-item"><a href="#">{$value}</a></li>
                        {/if}
                    {/foreach}
                    <li class="mytell-header-actions-inline">
                        <a class="" href="#" onclick="popUp('help/?id_nodo={if !empty($idSubMenu2Selected)}{$idSubMenu2Selected}&name_nodo={$nameSubMenu2Selected}{else}{$idSubMenuSelected}&name_nodo={$nameSubMenuSelected}{/if}','1000','460')">
                            <i class="ti ti-help"></i>
                        </a>
                    </li>
                    <li class="mytell-header-actions-inline dropdown">
                        <a id="togglestickynote1" href="#"><i class="ti ti-note"></i></a>
                    </li>
                </ol>
            </div>
            <div class="col-auto">
                <div class="btn-list">
                    {if $ISSABEL_PANELS}
                    <a href="#" id="header_open_sidebar" class="btn btn-icon" aria-label="Panels"><i class="ti ti-layout-sidebar"></i></a>
                    {/if}
                    <!-- Theme toggle -->
                    <a href="#" class="btn btn-icon" id="mytell-theme-toggle" aria-label="Toggle theme">
                        <i class="ti ti-moon" data-theme-icon></i>
                    </a>
                    <!-- Info dropdown -->
                    <div class="dropdown">
                        <a href="#" class="btn btn-icon" data-bs-toggle="dropdown" aria-label="Info"><i class="ti ti-info-circle"></i></a>
                        <div class="dropdown-menu dropdown-menu-end">
                            <a class="dropdown-item register_link" href="#">{$Registered}</a>
                            <a class="dropdown-item" href="#" id="viewDetailsRPMs"><i class="ti ti-box me-1"></i>{$VersionDetails}</a>
                            <a class="dropdown-item" href="https://github.com/DashSaman/MyTellPBX" target="_blank"><i class="ti ti-external-link me-1"></i>MyTellPBX Website</a>
                            <a class="dropdown-item" href="#" id="dialogaboutissabel"><i class="ti ti-info-circle me-1"></i>About MyTellPBX</a>
                        </div>
                    </div>
                    <!-- Notifications -->
                    <div class="dropdown">
                        <a href="#" class="btn btn-icon" data-bs-toggle="dropdown" aria-label="Notifications">
                            <i id='notibell' class="ti ti-bell {$ANIMATE_NOTIFICATION}"></i>
                        </a>
                        <div class="dropdown-menu dropdown-menu-end dropdown-menu-card">
                            <div class="px-3 pt-2 fw-bold">{$NOTIFICATIONS.LBL_NOTIFICATION_SYSTEM}</div>
                            {foreach from=$NOTIFICATIONS.NOTIFICATIONS_PUBLIC item=NOTI}
                                <a href="#" class="dropdown-item text-wrap
                                   {if $NOTI.level == "info"}text-info{elseif $NOTI.level == "warning"}text-warning{elseif $NOTI.level == "error"}text-danger{/if}"
                                   onclick='readNoti("{$NOTI.id}")'>
                                    <i class="{if $NOTI.level == "info"}ti ti-info-circle{elseif $NOTI.level == "warning"}ti ti-alert-triangle{elseif $NOTI.level == "error"}ti ti-ban{/if} me-1"></i>{$NOTI.content}
                                </a>
                            {foreachelse}
                                <div class="dropdown-item text-secondary small">{$NOTIFICATIONS.TXT_NO_NOTIFICATIONS}</div>
                            {/foreach}
                            <div class="px-3 pt-2 fw-bold">{$NOTIFICATIONS.LBL_NOTIFICATION_USER}</div>
                            {foreach from=$NOTIFICATIONS.NOTIFICATIONS_PRIVATE item=NOTI}
                                <a href="#" class="dropdown-item text-wrap
                                   {if $NOTI.level == "info"}text-info{elseif $NOTI.level == "warning"}text-warning{elseif $NOTI.level == "error"}text-danger{/if}">
                                    <i class="{if $NOTI.level == "info"}ti ti-info-circle{elseif $NOTI.level == "warning"}ti ti-alert-triangle{elseif $NOTI.level == "error"}ti ti-ban{/if} me-1"></i>{$NOTI.content}
                                </a>
                            {foreachelse}
                                <div class="dropdown-item text-secondary small">{$NOTIFICATIONS.TXT_NO_NOTIFICATIONS}</div>
                            {/foreach}
                        </div>
                    </div>
                    <!-- User menu -->
                    <div class="dropdown">
                        <a href="#" class="btn btn-icon px-2 d-flex align-items-center" data-bs-toggle="dropdown" aria-label="User menu">
                            <img src="index.php?menu=address_book&type=internal&action=getImage&idPhoto={$EXTENSION}&rawmode=yes&thumbnail=yes" alt=""
                                 class="avatar avatar-sm" onerror="this.style.display='none';" />
                            <span class="ms-1 d-none d-lg-inline">{$USER_LOGIN}</span>
                            <i class="ti ti-chevron-down ms-1"></i>
                        </a>
                        <div class="dropdown-menu dropdown-menu-end">
                            <a class="dropdown-item setadminpassword" href="#">
                                <i class="ti ti-user me-1"></i>{$CHANGE_PASSWORD}
                            </a>
                            <a class="dropdown-item" href="index.php?logout=yes">
                                <i class="ti ti-logout me-1"></i>{$LOGOUT}
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</header>

<!-- contenido del modulo-->
<div id="neo-contentbox">
    <div id="neo-contentbox-maincolumn" class="neo-module-content">
        <input type="hidden" id="issabel_framework_module_id" value="{if empty($idSubMenu2Selected)}{$idSubMenuSelected}{else}{$idSubMenu2Selected}{/if}" />
        <input type="hidden" id="issabel_framework_webCommon" value="{$WEBCOMMON}" />
        <input type="hidden" id="lblRegisterCm"   value="{$lblRegisterCm}" />
        <input type="hidden" id="lblRegisteredCm" value="{$lblRegisteredCm}" />
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
