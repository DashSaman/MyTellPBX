<!DOCTYPE html>
<html lang="en" data-bs-theme="light">
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>MyTellPBX</title>

    <link rel="icon" type="image/svg+xml" href="{$WEBPATH}themes/{$THEMENAME}/images/favicon.svg" />
    <link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/css/fonts.css" />
    <link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/css/tabler.min.css" />
    <link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/icons/tabler-icons.min.css" />
    <link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/css/glyphicons.min.css" />
    <link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/css/shell.css" />
    <link rel="stylesheet" href="{$WEBPATH}libs/js/sticky_note/sticky_note.css" />
    <link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/css/compat.css" />

    {$HEADER_LIBS_JQUERY}
    <script src="libs/js/base.js"></script>
    <script src="libs/js/sticky_note/sticky_note.js"></script>
    <script src="libs/js/iframe.js"></script>

    {$HEADER}
    {$HEADER_MODULES}
    </head>
    <body class="page-body" {$BODYPARAMS}>
    <div class="page page-container">

        {$MENU} <!-- Rendered from _menu.tpl: Tabler vertical sidebar + page header + open page body -->
                    {if !empty($mb_message)}
                    <div class="alert alert-danger alert-dismissible m-2" role="alert" id="message_error">
                        {if !empty($mb_title)}
                            <div class="alert-title">{$mb_title}</div>
                        {/if}
                        <div class="text-secondary">{$mb_message}</div>
                        <a class="btn-close" onclick="hide_message_error();"></a>
                    </div>
                    {/if}
                    {$CONTENT}
                    </div><!-- /neo-contentbox-maincolumn -->
                </div><!-- /page-body -->

        <!-- Footer -->
        <footer class="footer footer-transparent d-print-none mytell-footer">
            <div class="container-xl text-center">
                <a href="https://github.com/DashSaman/MyTellPBX" style="color: inherit; text-decoration: none;" target='_blank'><strong>MyTellPBX</strong></a>
                {$ISSABEL_LICENSED} <a href="http://www.opensource.org/licenses/gpl-license.php" target='_blank' style="color: inherit; text-decoration: none;">GPL</a>. 2006 - {$currentyear}.
            </div>
        </footer>
            </div><!-- /page-wrapper -->
        </div><!-- /page-container inner -->

        <div id="neo-sticky-note">
            <div id="neo-sticky-note-text"></div>
            <div id="neo-sticky-note-text-edit">
                <textarea id="neo-sticky-note-textarea"></textarea>
                <div id="neo-sticky-note-text-char-count"></div>
                <input type="button" class="btn btn-primary btn-sm" value="{$SAVE_NOTE}" id="neo-submit-button" />
                <div id="auto-popup">AutoPopUp <input type="checkbox" id="neo-sticky-note-auto-popup" value="1" /></div>
            </div>
            <div id="neo-sticky-note-text-edit-delete"></div>
        </div>
{* SE GENERA EL AUTO POPUP SI ESTA ACTIVADO *}
{if $AUTO_POPUP eq '1'}{literal}
<script type='text/javascript'>
$(document).ready(function(e) {
    $("#neo-sticky-note-auto-popup").prop('checked', true);
    $('#togglestickynote1').click();
});
</script>
{/literal}{/if}

        <!-- Neo Progress Bar (legacy popup box used by framework JS) -->
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
                    <a href="#" class="chat-close"><i class="ti ti-x"></i></a>
                    <i class="ti ti-list"></i>
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
    </div>
    <script src="{$WEBPATH}themes/{$THEMENAME}/js/shell.js"></script>
    </body>
</html>
