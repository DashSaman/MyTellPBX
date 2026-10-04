/* MyTel theme.js — shell behaviors that replace the old neon menu JS.
   Depends on jQuery + neon-api.js (toggle_sidebar_menu) + neon-custom.js (readNoti). */
(function ($) {
    "use strict";

    $(document).ready(function () {

        var $container = $('.page-container');

        /* burger (desktop collapse via neon helper, mobile drawer) */
        $('#mt-burger').on('click', function (e) {
            e.preventDefault();
            if (window.matchMedia('(max-width: 991px)').matches) {
                $container.toggleClass('mt-mobile-open');
            } else if (typeof toggle_sidebar_menu === 'function') {
                toggle_sidebar_menu(false);
            }
        });

        /* click outside closes the mobile drawer */
        $(document).on('click', function (e) {
            if ($container.hasClass('mt-mobile-open') &&
                !$(e.target).closest('#mt-sidebar, #mt-burger').length) {
                $container.removeClass('mt-mobile-open');
            }
        });

        /* panels drawer (original framework ids) */
        $(document).on('click', '#header_open_sidebar, a.chat-close', function (e) {
            $container.toggleClass('chat-visible');
            e.stopPropagation();
        });

        /* ---------- menu live search (filters top-level groups) ---------- */
        var norm = function (s) {
            return (s || '').replace(/[يى]/g, 'ی').replace(/ك/g, 'ک')
                     .replace(/\u200c/g, ' ').toLowerCase().trim();
        };
        var $search = $('#search_module_issabel');
        $search.on('input', function () {
            var q = norm($(this).val());
            $('#main-menu > li').each(function () {
                var $li = $(this);
                if ($li.attr('id') === 'search') return;
                var hit = q === '' || norm($li.text()).indexOf(q) !== -1;
                $li.toggle(hit);
                if (q !== '' && hit) $li.addClass('opened');
                if (q === '') $li.toggleClass('opened', $li.hasClass('active'));
            });
        });

        /* ---------- export dropdown from _list.tpl ---------- */
        $(document).on('click', '#neo-table-button-download-right', function (e) {
            e.stopPropagation();
            var $menu = $('#subMenuExport');
            var $btn = $('#export_button');
            if (!$menu.length || !$btn.length) return;
            if ($menu.hasClass('neo-display-none')) {
                var pos = $btn.position();
                var top = pos.top + $btn.outerHeight() + 2;
                var left = pos.left;
                if (left + $menu.outerWidth() > $(window).width() - 8) {
                    left = Math.max(8, $(window).width() - $menu.outerWidth() - 8);
                }
                $menu.css({ top: top + 'px', left: left + 'px' });
                $btn.addClass('exportBackground');
                $(this).addClass('exportBackground');
                $menu.removeClass('neo-display-none');
                $(this).attr('aria-expanded', 'true');
            } else {
                $menu.addClass('neo-display-none');
                $('#export_button').removeClass('exportBackground');
                $(this).removeClass('exportBackground');
                $(this).attr('aria-expanded', 'false');
            }
        });
        $(document).on('click', function (e) {
            if (!$(e.target).closest('#subMenuExport, #neo-table-button-download-right, #export_button').length) {
                $('#subMenuExport').addClass('neo-display-none');
                $('#export_button').removeClass('exportBackground');
                $('#neo-table-button-download-right').removeClass('exportBackground');
            }
        });
        $(document).on('click', '#neo-table-filter-button-arrow', function () {
            $(this).toggleClass('exportBackground');
        });

        /* guard against neon height fitting clipping the flex layout */
        var unclipTimer = null;
        var unclip = function () {
            $('.main-content.mt-main-content').css('height', 'auto');
        };
        setTimeout(unclip, 400);
        $(window).on('resize', function () {
            clearTimeout(unclipTimer);
            unclipTimer = setTimeout(unclip, 250);
        });
    });
})(jQuery);
