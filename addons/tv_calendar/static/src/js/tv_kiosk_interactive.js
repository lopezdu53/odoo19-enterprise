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

        // 3) Botones de estado (plantilla Pedidos de componentes).
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
    });
})();
