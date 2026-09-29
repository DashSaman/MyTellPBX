<li class="nav-item dropdown">
    {if $SHORTCUT_BOOKMARKS}
        <a class="nav-link dropdown-toggle" href="#navbar-menu-bookmarks" role="button" data-menu-group="navbar-menu-bookmarks" aria-expanded="false">
            <span class="nav-link-icon"><i class="ti ti-star"></i></span>
            <span class="nav-link-title">{$SHORTCUT_BOOKMARKS_LABEL}</span>
        </a>
        <div class="dropdown-menu" id="navbar-menu-bookmarks">
            {foreach from=$SHORTCUT_BOOKMARKS item=shortcut name=shortcut}
                <a class="dropdown-item" href="index.php?menu={$shortcut.namemenu}">
                    {$shortcut.name}
                </a>
            {/foreach}
        </div>
    {/if}
</li>

<li class="nav-item dropdown">
    <a class="nav-link dropdown-toggle" href="#navbar-menu-history" role="button" data-menu-group="navbar-menu-history" aria-expanded="false">
        <span class="nav-link-icon"><i class="ti ti-history"></i></span>
        <span class="nav-link-title">{$SHORTCUT_HISTORY_LABEL}</span>
    </a>
    <div class="dropdown-menu" id="navbar-menu-history">
        {foreach from=$SHORTCUT_HISTORY item=shortcut}
            <a class="dropdown-item" href="index.php?menu={$shortcut.namemenu}">
                {$shortcut.name}
            </a>
        {/foreach}
    </div>
</li>
