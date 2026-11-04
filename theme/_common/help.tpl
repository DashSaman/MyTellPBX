<html>
  <head>
    <title>{$titulo|escape:html}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <script src="{$WEBPATH}themes/{$THEMENAME}/js/appearance.js?v=740"></script>
    <link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/help.css?v=740" />
  </head>
  <frameset cols="20%,80%" border="1" >
    <frame src="frameLeft.php?id_nodo={$id_nodo}" name="navegacion" noresize>
    <frame src="frameRight.php?id_nodo={$id_nodo}&name_nodo={$name_nodo}" name="contenido" class="mainHelp" noresize>
  </frameset>
</html>
