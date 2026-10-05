/* Interactividad de las plantillas Electricos y Pedidos de componentes.
   Se sirve como archivo estatico publico y se carga desde el kiosco. */
(function () {
    "use strict";

    function pad(n) { return (n < 10 ? "0" : "") + n; }
    function fmtTs(ts) {
        var d = new Date(ts * 1000);
        var h = d.getHours();
        var ap = h < 12 ? "am" : "pm";
        var h12 = h % 12; if (h12 === 0) { h12 = 12; }
        return pad(d.getDate()) + "/" + pad(d.getMonth() + 1) + " " +
            pad(h12) + ":" + pad(d.getMinutes()) + " " + ap;
    }

    function ready(fn) {
        if (document.readyState !== "loading") { fn(); }
        else { document.addEventListener("DOMContentLoaded", fn); }
    }

    ready(function () {
        var dataEl = document.getElementById("tvc-data");
        var token = dataEl ? dataEl.getAttribute("data-token") : "";

        // 1) Convertir cualquier [data-ts] a hora local del dispositivo.
        Array.prototype.forEach.call(document.querySelectorAll("[data-ts]"), function (el) {
            var ts = parseInt(el.getAttribute("data-ts"), 10);
            if (ts) { el.textContent = fmtTs(ts); }
        });

        // 2) Modal de "Solicitar componente" (plantilla Electricos).
        var modal = document.getElementById("req-modal");
        if (modal && token) {
            var catSel = document.getElementById("req-cat");
            var prodSel = document.getElementById("req-prod");
            var msg = document.getElementById("req-msg");
            var currentTask = null;

            function opt(value, text) {
                var o = document.createElement("option");
                o.value = value; o.textContent = text;
                return o;
            }
            function openModal(taskId) {
                currentTask = taskId; msg.textContent = "";
                prodSel.innerHTML = "";
                modal.style.display = "flex";
                catSel.innerHTML = ""; catSel.appendChild(opt("", "Cargando..."));
                fetch("/tv/component/categories/" + token)
                    .then(function (r) { return r.json(); })
                    .then(function (d) {
                        catSel.innerHTML = "";
                        catSel.appendChild(opt("", "-- Categoria --"));
                        (d.categories || []).forEach(function (c) {
                            catSel.appendChild(opt(c.id, c.name));
                        });
                    })
                    .catch(function () { msg.textContent = "Error cargando categorias"; });
            }
            function closeModal() { modal.style.display = "none"; }
            function loadProducts() {
                var cid = catSel.value;
                prodSel.innerHTML = "";
                if (!cid) { return; }
                prodSel.appendChild(opt("", "Cargando..."));
                fetch("/tv/component/products/" + token + "/" + cid)
                    .then(function (r) { return r.json(); })
                    .then(function (d) {
                        prodSel.innerHTML = "";
                        prodSel.appendChild(opt("", "-- Producto --"));
                        (d.products || []).forEach(function (p) {
                            prodSel.appendChild(opt(p.id, p.name + "  ($" + p.price + ")"));
                        });
                    })
                    .catch(function () { msg.textContent = "Error cargando productos"; });
            }
            catSel.addEventListener("change", loadProducts);
            document.getElementById("req-cancel").addEventListener("click", closeModal);
            document.getElementById("req-send").addEventListener("click", function () {
                var pid = prodSel.value;
                if (!pid) { msg.textContent = "Selecciona un producto."; return; }
                var fd = new FormData();
                fd.append("product_id", pid);
                if (currentTask) { fd.append("task_id", currentTask); }
                fetch("/tv/component/request/" + token, { method: "POST", body: fd })
                    .then(function (r) { return r.json(); })
                    .then(function (d) {
                        if (d.ok) {
                            msg.textContent = "Solicitud enviada ✓";
                            setTimeout(closeModal, 1200);
                        } else {
                            msg.textContent = "Error: " + (d.error || "");
                        }
                    })
                    .catch(function () { msg.textContent = "Error de conexion."; });
            });
            Array.prototype.forEach.call(document.querySelectorAll(".req-btn"), function (b) {
                b.addEventListener("click", function () {
                    openModal(b.getAttribute("data-task"));
                });
            });
        }

        // 3b) Cronometro + botones de tarea (plantilla Electricos).
        function fmtDur(s) {
            s = Math.max(0, Math.floor(s));
            var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
            return pad(h) + ":" + pad(m) + ":" + pad(sec);
        }
        function renderTimers() {
            Array.prototype.forEach.call(document.querySelectorAll(".et-timer"), function (el) {
                var base = parseInt(el.getAttribute("data-elapsed"), 10) || 0;
                var run = parseInt(el.getAttribute("data-running"), 10) || 0;
                var total = run ? (base + (Date.now() / 1000 - run)) : base;
                el.textContent = fmtDur(total);
            });
        }
        function setTaskButtons(ctrl, state) {
            ctrl.setAttribute("data-state", state);
            var start = ctrl.querySelector(".tb-start");
            var pause = ctrl.querySelector(".tb-pause");
            var done = ctrl.querySelector(".tb-done");
            if (start) {
                start.disabled = (state === "in_progress" || state === "done");
                start.textContent = (state === "paused" ? "▶ Reanudar" : "▶ Iniciar");
            }
            if (pause) { pause.disabled = (state !== "in_progress"); }
            if (done) { done.disabled = (state === "assigned" || state === "done"); }
        }
        function setStamp(id, ts) {
            var el = document.getElementById(id);
            if (el && ts) { el.textContent = fmtTs(ts); }
        }
        if (document.querySelector(".et-timer")) {
            renderTimers();
            setInterval(renderTimers, 1000);
        }
        Array.prototype.forEach.call(document.querySelectorAll(".et-controls"), function (ctrl) {
            setTaskButtons(ctrl, ctrl.getAttribute("data-state") || "assigned");
        });
        if (token) {
            Array.prototype.forEach.call(document.querySelectorAll(".task-btn"), function (b) {
                b.addEventListener("click", function () {
                    if (b.disabled) { return; }
                    var id = b.getAttribute("data-task");
                    var action = b.getAttribute("data-action");
                    var ctrl = b.parentNode;
                    b.disabled = true;
                    fetch("/tv/task/action/" + token + "/" + id + "/" + action, { method: "POST" })
                        .then(function (r) { return r.json(); })
                        .then(function (d) {
                            if (!d.ok) { setTaskButtons(ctrl, ctrl.getAttribute("data-state")); return; }
                            var timer = document.getElementById("timer-" + id);
                            if (timer) {
                                timer.setAttribute("data-elapsed", d.elapsed);
                                timer.setAttribute("data-running", d.running_ts || 0);
                            }
                            setStamp("st-start-" + id, d.started_ts);
                            setStamp("st-pause-" + id, d.paused_ts);
                            setStamp("st-react-" + id, d.reactivated_ts);
                            setStamp("st-done-" + id, d.completed_ts);
                            setTaskButtons(ctrl, d.state);
                            renderTimers();
                        })
                        .catch(function () { setTaskButtons(ctrl, ctrl.getAttribute("data-state")); });
                });
            });
        }

        // 4) Botones de estado (plantilla Pedidos de componentes).
        if (token) {
            Array.prototype.forEach.call(document.querySelectorAll(".comp-btn"), function (b) {
                b.addEventListener("click", function () {
                    if (b.disabled) { return; }
                    var id = b.getAttribute("data-id");
                    var state = b.getAttribute("data-state");
                    b.disabled = true;
                    fetch("/tv/component/state/" + token + "/" + id + "/" + state,
                        { method: "POST" })
                        .then(function (r) { return r.json(); })
                        .then(function (d) {
                            if (d.ok) {
                                b.classList.add("done");
                                var key = (state === "requested" ? "req" : "del") + "-" + id;
                                var tsEl = document.getElementById("ts-" + key);
                                if (tsEl) { tsEl.textContent = fmtTs(d.ts); }
                            } else {
                                b.disabled = false;
                            }
                        })
                        .catch(function () { b.disabled = false; });
                });
            });
        }

        // 5) Visor de planos PDF (plantilla Planos).
        var planoOv = document.getElementById("plano-ov");
        if (planoOv && token && window.pdfjsLib) {
            var workerSrc = dataEl ? dataEl.getAttribute("data-worker") : "";
            if (workerSrc) {
                pdfjsLib.GlobalWorkerOptions.workerSrc = workerSrc;
            }
            var pagesEl = document.getElementById("plano-pages");
            var zEl = document.getElementById("plano-zlvl");
            var pdfDoc = null;
            var scale = 1.3;      // escala base (ajuste comodo en TV)
            var BASE = 1.3;

            function showZoom() {
                if (zEl) { zEl.textContent = Math.round((scale / BASE) * 100) + "%"; }
            }
            function renderAll() {
                if (!pdfDoc) { return; }
                pagesEl.innerHTML = "";
                showZoom();
                for (var i = 1; i <= pdfDoc.numPages; i++) {
                    renderPage(i);
                }
            }
            function renderPage(num) {
                pdfDoc.getPage(num).then(function (page) {
                    var vp = page.getViewport({ scale: scale });
                    var canvas = document.createElement("canvas");
                    canvas.className = "plano-canvas";
                    canvas.width = vp.width;
                    canvas.height = vp.height;
                    pagesEl.appendChild(canvas);
                    page.render({ canvasContext: canvas.getContext("2d"), viewport: vp });
                });
            }
            function openPlano(taskId) {
                planoOv.style.display = "flex";
                pagesEl.innerHTML = "<div class='plano-load'>Cargando plano...</div>";
                scale = BASE;
                pdfjsLib.getDocument("/tv/plano/" + token + "/" + taskId).promise
                    .then(function (doc) {
                        pdfDoc = doc;
                        renderAll();
                    })
                    .catch(function () {
                        pagesEl.innerHTML = "<div class='plano-load'>No se pudo abrir el plano.</div>";
                    });
            }
            function closePlano() {
                planoOv.style.display = "none";
                pagesEl.innerHTML = "";
                pdfDoc = null;
            }
            document.getElementById("plano-close").addEventListener("click", closePlano);
            document.getElementById("plano-zin").addEventListener("click", function () {
                scale = Math.min(6, scale + 0.3); renderAll();
            });
            document.getElementById("plano-zout").addEventListener("click", function () {
                scale = Math.max(0.4, scale - 0.3); renderAll();
            });
            Array.prototype.forEach.call(document.querySelectorAll(".plano-btn"), function (b) {
                b.addEventListener("click", function () {
                    openPlano(b.getAttribute("data-plano"));
                });
            });
        }
    });
})();
