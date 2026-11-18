{* Match the installed shell's list navigation, not the retired Tabler navbar. *}
<li>
    {if $SHORTCUT_BOOKMARKS}
        <a href="#">
            <i class="fa fa-star"></i>
            <span>{$SHORTCUT_BOOKMARKS_LABEL}</span>
        </a>
        <ul>
            {foreach from=$SHORTCUT_BOOKMARKS item=shortcut name=shortcut}
                {if $shortcut.namemenu != 'language'}
                <li>
                    <a href="index.php?menu={$shortcut.namemenu}">
                        <span>{$shortcut.name}</span>
                    </a>
                </li>
                {/if}
            {/foreach}
        </ul>
    {/if}
</li>
<li>
    <a href="#">
        <i class="fa fa-history"></i>
        <span>{$SHORTCUT_HISTORY_LABEL}</span>
    </a>
    <ul>
        {foreach from=$SHORTCUT_HISTORY item=shortcut}
            {if $shortcut.namemenu != 'language'}
            <li>
                <a href="index.php?menu={$shortcut.namemenu}">
                    <span>{$shortcut.name}</span>
                </a>
            </li>
            {/if}
        {/foreach}
    </ul>
</li>
