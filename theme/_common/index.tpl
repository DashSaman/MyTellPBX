<!DOCTYPE html>
<html lang="{$LANG}" dir="{$THEME_DIR}">
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{$BRAND_NAME} | {$BRAND_TAGLINE}</title>
    <link rel="shortcut icon" href="{$WEBPATH}themes/{$THEMENAME}/images/favicon.png" />
    <link rel="icon" type="image/svg+xml" href="{$WEBPATH}themes/{$THEMENAME}/images/mytel-emblem.svg" />

    <link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/css/fonts.css?v=30">
    <link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/css/glyphicons.css?v=30">
    <link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/css/tokens.css?v=30">
    <link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/css/base.css?v=30">
    <link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/css/components.css?v=30">
    <link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/css/applet.css?v=30">
    <link rel="stylesheet" media="screen" type="text/css" href="{$WEBPATH}libs/js/sticky_note/sticky_note.css" >

    {$HEADER_LIBS_JQUERY}
    {literal}
    <script>
    /* MyTel chart brand remap — intercepts flot assignment itself, so the
       wrapper is installed no matter when the chart library loads. */
    (function () {
        var MAP = {'#33cc33':'#27965A','#00cc00':'#27965A','#3da8fb':'#1E88E5','#2da8fb':'#1E88E5','#cb4b4b':'#FF8A00','#e8b800':'#FF8A00','#0000cc':'#1E88E5','#cc0000':'#FF8A00','#edc240':'#FF8A00','#afd8f8':'#1E88E5'};
        function remap(c) { if (typeof c !== 'string') return c; var k = c.toLowerCase(); return MAP[k] || c; }
        var WD = ['یکشنبه','دوشنبه','سه‌شنبه','چهارشنبه','پنجشنبه','جمعه','شنبه'];
        function faTick(v, axis) {
            var d = new Date(v);
            var span = axis.datamax - axis.datamin;
            var hm = ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
            if (span > 250 * 864e5) {
                var j = window.MTJalali ? window.MTJalali.toJalali(d) : null;
                return j ? (window.MTJalali.JMONTHS[j.jm - 1] + ' ' + window.MTJalali.faNum(j.jy)) : (d.getFullYear() + '/' + (d.getMonth() + 1));
            }
            if (span > 3 * 864e5) return WD[d.getDay()] + ' ' + hm;
            return hm;
        }
        function wrap(orig) {
            var f = function (el, data, opts) {
                try {
                    if (data && data.map) data = data.map(function (s) { if (s && s.color) s.color = remap(s.color); return s; });
                    if (opts && opts.colors) opts.colors = opts.colors.map(remap);
                    if (opts && opts.yaxes) opts.yaxes.forEach(function (ax) { if (ax && ax.font) ax.font.color = remap(ax.font.color); });
                    if (opts && opts.xaxes) opts.xaxes.forEach(function (ax) {
                        if (ax && ax.mode === 'time' && !ax.tickFormatter) ax.tickFormatter = faTick;
                    });
                } catch (e) {}
                return orig.apply(this, arguments);
            };
            /* flot reads $.plot.plugins — carry every own property over */
            for (var k in orig) { if (Object.prototype.hasOwnProperty.call(orig, k)) f[k] = orig[k]; }
            f.__mt = true;
            return f;
        }
        var iv = setInterval(function () {
            if (!window.jQuery || jQuery.plot === undefined || jQuery.plot === null) return;
            if (jQuery.plot.__mt) { clearInterval(iv); return; }
            try {
                var real = jQuery.plot;
                Object.defineProperty(jQuery, 'plot', {
                    configurable: true,
                    get: function () { return real.__mt ? real : (real = wrap(real)); },
                    set: function (fn) { real = fn && fn.__mt ? fn : wrap(fn); }
                });
            } catch (e) { jQuery.plot = wrap(jQuery.plot); }
            clearInterval(iv);
        }, 5);
        setTimeout(function () { clearInterval(iv); }, 15000);
    })();
    </script>
    {/literal}
    <script src="libs/js/base.js"></script>
    <script src="libs/js/sticky_note/sticky_note.js"></script>
    <script src="libs/js/iframe.js"></script>

    {$HEADER}
    {$HEADER_MODULES}
    </head>
    <body leftmargin="0" topmargin="0" marginwidth="0" marginheight="0" class="mt-body page-body" {$BODYPARAMS}>
    <div class="page-container mt-shell">

        {$MENU}
                    {if !empty($mb_message)}
                    <div class="div_msg_errors mt-alert-error" id="message_error">
                    {if !empty($mb_title)}
                        <div class="div_msg_errors_title">
                            <b style="color:red;">&nbsp;{$mb_title}</b>
                        </div>
                    {/if}
                        <div class="div_msg_errors_dismiss"><i class="fa fa-lg fa-remove" onclick="hide_message_error();"></i></div>
                        <div class="div_msg_errors_content" {if empty($mb_title)}style="margin-left: 0;"{/if}>{$mb_message}</div>
                    </div>
                    {/if}
                    {$CONTENT}
                </div>
            </div>
        </div><!-- neo-contentbox -->

        <!-- Footer -->
        <footer class="mt-footer">
            <span class="mt-footer-brand">{$BRAND_NAME}</span>
            <span class="mt-footer-sep">&bull;</span>
            <span>{$BRAND_TAGLINE}</span>
            <span class="mt-footer-year">&copy; {$currentyear}</span>
        </footer>

        </div><!-- main-content -->

        <div id="neo-sticky-note">
            <div id="neo-sticky-note-text"></div>
            <div id="neo-sticky-note-text-edit">
                <textarea id="neo-sticky-note-textarea"></textarea>
                <div id="neo-sticky-note-text-char-count"></div>
                <input type="button" value="{$SAVE_NOTE}" id="neo-submit-button" />
                <div id="auto-popup">AutoPopUp <input type="checkbox" id="neo-sticky-note-auto-popup" value="1" /></div>
            </div>
            <div id="neo-sticky-note-text-edit-delete"></div>
        </div>
{if $AUTO_POPUP eq '1'}{literal}
<script type='text/javascript'>
$(document).ready(function(e) {
    $("#neo-sticky-note-auto-popup").prop('checked', true);
    $('#togglestickynote1').click();
});
</script>
{/literal}{/if}

        <!-- Progress popup -->
        <div class="neo-modal-issabel-popup-box">
            <div class="neo-modal-issabel-popup-title"></div>
            <div class="neo-modal-issabel-popup-close"></div>
            <div class="neo-modal-issabel-popup-content"></div>
        </div>
        <div class="neo-modal-issabel-popup-blockmask"></div>
{if $ISSABEL_PANELS}
        <div id="chat" class="fixed">
            <div class="chat-inner">
                <h2 class="chat-header">
                    <a href="#" class="chat-close"><i class="fa fa-remove"></i></a>
                    <i class="fa fa-th-list"></i>
                    <span id="panel-header-text">{$LBL_ISSABEL_PANELS_SIDEBAR|escape:html}</span>
                </h2>
                <div id="issabel-panels" class="panel-group joined">
                    {foreach from=$ISSABEL_PANELS key=panelname item=paneldata name=issabelpanel}
                    <div class="panel">
                        <div class="panel-heading">
                            <h4 class="panel-title">
                                <a data-toggle="collapse" data-parent="#issabel-panels" href="#issabel-panel-{$panelname}">
                                    {if $paneldata.iconclass}
                                    <i class="{$paneldata.iconclass}"></i>
                                    {elseif $paneldata.icon}
                                    <div style="display: inline-block; min-width: 15px; min-height: 15px; padding-right: 5px;">
                                    <img alt="" src="{$paneldata.icon}" width="15" />
                                    </div>
                                    {else}
                                    <i class="fa fa-file-o"></i>
                                    {/if}
                                    <span>{$paneldata.title|escape:html}</span>
                                </a>
                            </h4>
                        </div>
                        <div id="issabel-panel-{$panelname}" class="panel-collapse collapse{if $smarty.foreach.issabelpanel.first} in{/if}">
                            <div class="panel-body">{$paneldata.content}</div>
                        </div>
                    </div>
                    {/foreach}
                </div>
            </div>
        </div>
{/if}
        <!-- Bottom Scripts -->
        <script src="{$WEBPATH}themes/{$THEMENAME}/js/gsap/main-gsap.js"></script>
        <script src="{$WEBPATH}themes/{$THEMENAME}/js/bootstrap.js"></script>
        <script src="{$WEBPATH}themes/{$THEMENAME}/js/joinable.js"></script>
        <script src="{$WEBPATH}themes/{$THEMENAME}/js/resizeable.js"></script>
        <script src="{$WEBPATH}themes/{$THEMENAME}/js/neon-api.js"></script>
        <script src="{$WEBPATH}themes/{$THEMENAME}/js/jquery.validate.min.js"></script>
        <script src="{$WEBPATH}themes/{$THEMENAME}/js/loadingoverlay.js"></script>
        <script src="{$WEBPATH}themes/{$THEMENAME}/js/iframe-show-loader.js"></script>
        <script src="{$WEBPATH}themes/{$THEMENAME}/js/neon-custom.js"></script>
        <script src="{$WEBPATH}themes/{$THEMENAME}/vendor/echarts/echarts.min.js"></script>
        <script src="{$WEBPATH}themes/{$THEMENAME}/js/mytel-charts.js?v=10"></script>
        <script src="{$WEBPATH}themes/{$THEMENAME}/js/theme.js?v=30"></script>
    </div>
</body>
</html>
