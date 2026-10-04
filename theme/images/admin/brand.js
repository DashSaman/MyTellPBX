/* MyTel brand text layer for the IssabelPBX admin (presentation-only substitution). */
(function () {
    "use strict";
    var MAP = { "IssabelPBX": "MyTel PBX", "Issabel PBX": "MyTel PBX", "FreePBX": "MyTel PBX" };

    function swap(root) {
        var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null, false);
        var node, text, changed;
        while ((node = walker.nextNode())) {
            text = node.nodeValue;
            if (!text || text.indexOf("Issabel") === -1) continue;
            changed = text;
            Object.keys(MAP).forEach(function (k) {
                changed = changed.split(k).join(MAP[k]);
            });
            if (changed !== text) node.nodeValue = changed;
        }
    }

    function run() {
        if (document.title.indexOf("Issabel") !== -1) {
            Object.keys(MAP).forEach(function (k) {
                document.title = document.title.split(k).join(MAP[k]);
            });
        }
        swap(document.body);
    }

    document.addEventListener("DOMContentLoaded", run);
    window.addEventListener("load", run);
    setInterval(run, 2000);
})();
