/**
 * Vehículo · importes: formato español sin alterar valores.
 *
 * Formato visual:  1.234.567,89  (punto miles, coma decimal)
 * Formato envío:   1234567.89    (decimal estándar para Django)
 *
 * Regla de interpretación (parseValor):
 *   - Si hay coma: los puntos son separadores de miles ("7.500,50" → 7500.50).
 *   - Si hay varios puntos: son separadores de miles ("1.234.567" → 1234567).
 *   - Si hay un único punto:
 *        con 3 cifras detrás → separador de miles ("7.500" → 7500)
 *        con 1-2 cifras      → decimal ("7500.5" → 7500.5)
 *
 * No se reformatea mientras se escribe: se formatea al salir del campo y antes
 * de enviar. Así no hay saltos de cursor ni multiplicaciones por 100 al
 * interpretar como español un número que ya estaba en formato estándar.
 */
(function () {
    'use strict';

    var CAMPOS_COSTE = ['id_precio_subasta', 'id_tasas_sala', 'id_logistica_grua'];
    var CAMPOS_IMPORTE = CAMPOS_COSTE.concat(['id_precio_venta', 'id_tipo_iva']);
    var ID_TASA = 'id_tipo_iva_rate';

    /** Texto escrito por el usuario → "1234.56" (o '' si no hay número). */
    function parseValor(texto) {
        if (texto === null || texto === undefined) return '';
        var s = String(texto).replace(/[^\d.,-]/g, '').trim();
        if (!s) return '';
        var negativo = s.charAt(0) === '-';
        if (negativo) s = s.substring(1);

        if (s.indexOf(',') !== -1) {
            // Formato español: puntos = miles, coma = decimal
            s = s.replace(/\./g, '').replace(',', '.');
        } else {
            var puntos = s.split('.').length - 1;
            if (puntos > 1) {
                s = s.replace(/\./g, '');
            } else if (puntos === 1) {
                var partes = s.split('.');
                if (partes[1].length === 3) {
                    // "7.500" es siete mil quinientos, no 7,5
                    s = partes[0] + partes[1];
                }
            }
        }
        return (negativo ? '-' : '') + s;
    }

    /** "1234567.89" → "1.234.567,89" */
    function formatEspanol(numero) {
        var s = String(numero === null || numero === undefined ? '' : numero).trim();
        if (!s) return '';
        var negativo = s.charAt(0) === '-';
        if (negativo) s = s.substring(1);

        var partes = s.split('.');
        var entero = partes[0] || '0';
        var decimales = partes.length > 1 ? partes[1].substring(0, 2) : '';

        entero = entero.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
        var resultado = decimales ? entero + ',' + decimales : entero;
        return (negativo ? '-' : '') + resultado;
    }

    function formatearCampo(el) {
        var limpio = parseValor(el.value);
        if (limpio !== '') {
            el.value = formatEspanol(limpio);
        }
    }

    /* ── Totales ──────────────────────────────────────────────────── */

    function calcularTotal() {
        var display = document.getElementById('coste-inicial-display');
        if (!display) return;
        var total = 0;
        for (var i = 0; i < CAMPOS_COSTE.length; i++) {
            var el = document.getElementById(CAMPOS_COSTE[i]);
            if (!el) continue;
            var valor = parseFloat(parseValor(el.value));
            if (!isNaN(valor)) total += valor;
        }
        display.textContent = '€' + total.toFixed(2).replace('.', ',');
    }

    function calcularIVA() {
        var tasas = document.getElementById('id_tasas_sala');
        var logistica = document.getElementById('id_logistica_grua');
        var tasa = document.getElementById(ID_TASA);
        var iva = document.getElementById('id_tipo_iva');
        if (!tasas || !logistica || !tasa || !iva) return;

        var base = (parseFloat(parseValor(tasas.value)) || 0) +
                   (parseFloat(parseValor(logistica.value)) || 0);
        var porcentaje = parseFloat(tasa.value) || 0;
        iva.value = formatEspanol((base * porcentaje / 100).toFixed(2));
    }

    /* ── Formatear al salir del campo ─────────────────────────────── */

    function alEntrar(el) {
        // Al enfocar se muestra el valor "crudo" para poder editarlo cómodo
        var limpio = parseValor(el.value);
        if (limpio !== '') el.value = limpio;
    }

    function alSalir(el) {
        formatearCampo(el);
        calcularTotal();
    }

    /* ── Envío: solo con el botón Guardar ─────────────────────────── */

    /** Enter dentro de un campo NO envía el formulario.
     *
     * El navegador envía el formulario al pulsar Enter en un input (envío
     * implícito): eso guardaba y generaba un asiento sin que el usuario
     * terminara de corregir el resto de importes. Se permite Enter en el
     * textarea (saltos de línea) y en los botones (su acción normal).
     */
    function bloquearEnter(evento) {
        if (evento.key !== 'Enter') return;
        var el = evento.target;
        if (!el) return;
        if (el.tagName === 'TEXTAREA' || el.tagName === 'BUTTON') return;
        evento.preventDefault();
    }

    function limpiarAntesDeEnviar() {
        for (var i = 0; i < CAMPOS_IMPORTE.length; i++) {
            var el = document.getElementById(CAMPOS_IMPORTE[i]);
            if (el) el.value = parseValor(el.value);
        }
        // Evita un segundo envío (crearía otro asiento) mientras guarda
        var boton = document.querySelector('button[type="submit"]');
        if (boton) {
            boton.disabled = true;
            boton.textContent = 'Guardando…';
        }
    }

    /* ── Init ─────────────────────────────────────────────────────── */

    document.addEventListener('DOMContentLoaded', function () {
        for (var i = 0; i < CAMPOS_IMPORTE.length; i++) {
            var el = document.getElementById(CAMPOS_IMPORTE[i]);
            if (!el) continue;
            formatearCampo(el);
            el.addEventListener('focus', function (evento) { alEntrar(evento.target); });
            el.addEventListener('blur', function (evento) { alSalir(evento.target); });
            el.addEventListener('input', calcularTotal);
        }

        var tasa = document.getElementById(ID_TASA);
        if (tasa) {
            tasa.addEventListener('change', function () {
                calcularIVA();
                calcularTotal();
            });
        }

        var formulario = document.querySelector('form');
        if (formulario) {
            formulario.addEventListener('keydown', bloquearEnter);
            formulario.addEventListener('submit', limpiarAntesDeEnviar);
        }

        calcularTotal();
    });
})();
