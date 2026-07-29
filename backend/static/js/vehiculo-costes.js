/**
 * Vehiculo costes: formateo numerico espanol + calculo automatico.
 *
 * Formato visual:  1.234.567,89  (punto miles, coma decimal)
 * Formato envio:   1234567.89    (decimal estandar para Django)
 *
 * Auto-calcula: coste_inicial = precio_subasta + tasas_sala + logistica_grua
 */
(function () {
    'use strict';

    var FIELD_IDS = ['id_precio_subasta', 'id_tasas_sala', 'id_logistica_grua'];
    var PERCENTAGE_FIELD_IDS = ['id_tipo_iva'];
    var IVA_RATE_ID = 'id_tipo_iva_rate';
    var display;

    /* ── Formateo espanol ─────────────────────────────────────────── */

    /** "1234567.89" → "1.234.567,89" */
    function formatSpanish(numStr) {
        if (!numStr || numStr === '') return '';
        var negative = numStr.charAt(0) === '-';
        if (negative) numStr = numStr.substring(1);

        var hasTrailingDot = numStr.charAt(numStr.length - 1) === '.';
        var parts = numStr.split('.');
        var intPart = parts[0] || '0';
        var decPart = parts.length > 1 ? parts[1] : '';

        // Puntos de miles en la parte entera
        intPart = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.');

        var result = intPart;
        if (decPart !== '') {
            result += ',' + decPart;
        } else if (hasTrailingDot) {
            result += ',';
        }
        return negative ? '-' + result : result;
    }

    /** "1.234.567,89" → "1234567.89"  (para envio a Django) */
    function parseSpanish(str) {
        if (!str || str === '') return '';
        return str.replace(/%/g, '').replace(/\./g, '').replace(',', '.');
    }

    /** Extrae solo digitos, un punto y hasta 2 decimales del valor crudo */
    function extractRaw(val) {
        // Permitir solo: digitos, un punto decimal, signo menos al inicio
        var cleaned = val.replace(/[^\d.\-]/g, '');
        // Solo un punto
        var firstDot = cleaned.indexOf('.');
        if (firstDot !== -1) {
            cleaned = cleaned.substring(0, firstDot + 1) +
                      cleaned.substring(firstDot + 1).replace(/\./g, '');
            // Max 2 decimales despues del punto
            var afterDot = cleaned.substring(firstDot + 1);
            if (afterDot.length > 2) {
                cleaned = cleaned.substring(0, firstDot + 1) + afterDot.substring(0, 2);
            }
        }
        return cleaned;
    }

    /* ── Auto-calcular coste inicial ──────────────────────────────── */

    function calculateTotal() {
        if (!display) return;
        var total = 0;
        for (var i = 0; i < FIELD_IDS.length; i++) {
            var el = document.getElementById(FIELD_IDS[i]);
            if (el) {
                var raw = parseSpanish(el.value);
                var val = parseFloat(raw);
                if (!isNaN(val)) total += val;
            }
        }
        display.textContent = '\u20AC' + total.toFixed(2).replace('.', ',');
    }

    /* ── Auto-calcular IVA desde base_imponible (tasas + logistica) x tasa ── */

    function calcularIVA() {
        var tasasEl = document.getElementById('id_tasas_sala');
        var logisEl = document.getElementById('id_logistica_grua');
        var rateEl = document.getElementById(IVA_RATE_ID);
        var ivaEl = document.getElementById('id_tipo_iva');
        if (!tasasEl || !logisEl || !rateEl || !ivaEl) return;

        var base = (parseFloat(parseSpanish(tasasEl.value)) || 0) +
                   (parseFloat(parseSpanish(logisEl.value)) || 0);
        var tasa = parseFloat(rateEl.value) || 0;
        var iva = base * tasa / 100;
        ivaEl.value = formatSpanish(iva.toFixed(2));
    }

    /* ── Formatear al escribir ────────────────────────────────────── */

    function handleInput(e) {
        var el = e.target;
        var cursorFromEnd = el.value.length - el.selectionStart;

        // Primero parsear formato español (quitar puntos miles, coma→punto), luego limpiar
        var raw = extractRaw(parseSpanish(el.value));
        var formatted = formatSpanish(raw);

        el.value = formatted;

        // Restaurar posicion del cursor
        var newCursorPos = formatted.length - cursorFromEnd;
        if (newCursorPos < 0) newCursorPos = 0;
        el.setSelectionRange(newCursorPos, newCursorPos);

        calculateTotal();
        calcularIVA();
    }

    /* ── Pre-cargar formato al iniciar ────────────────────────────── */

    function precacheFormat() {
        var allIds = FIELD_IDS.concat(PERCENTAGE_FIELD_IDS);
        for (var i = 0; i < allIds.length; i++) {
            var el = document.getElementById(allIds[i]);
            if (el && el.value) {
                var raw = el.value;
                if (raw.indexOf('.') !== -1 && raw.indexOf(',') === -1) {
                    el.value = formatSpanish(raw);
                }
            }
        }
        calculateTotal();
        calcularIVA();
    }

    /* ── Limpiar formato antes de enviar ──────────────────────────── */

    function cleanBeforeSubmit() {
        var allIds = FIELD_IDS.concat(PERCENTAGE_FIELD_IDS);
        for (var i = 0; i < allIds.length; i++) {
            var el = document.getElementById(allIds[i]);
            if (el) {
                el.value = parseSpanish(el.value);
            }
        }
    }

    /* ── Init ─────────────────────────────────────────────────────── */

    document.addEventListener('DOMContentLoaded', function () {
        display = document.getElementById('coste-inicial-display');

        var allIds = FIELD_IDS.concat(PERCENTAGE_FIELD_IDS);
        for (var i = 0; i < allIds.length; i++) {
            var el = document.getElementById(allIds[i]);
            if (el) {
                el.addEventListener('input', handleInput);
                el.addEventListener('change', handleInput);
            }
        }

        // Evento para cambio de tasa IVA
        var rateEl = document.getElementById(IVA_RATE_ID);
        if (rateEl) {
            rateEl.addEventListener('change', function () {
                calcularIVA();
            });
        }

        precacheFormat();

        // Limpiar antes de enviar el formulario
        var form = document.querySelector('form');
        if (form) {
            form.addEventListener('submit', cleanBeforeSubmit);
        }
    });
})();
