/**
 * Auto-calculation of "Coste Inicial Total" in the vehicle form.
 * Sums precio_subasta + tasas_sala + logistica_grua in real time.
 */
(function () {
    var fieldIds = ['id_precio_subasta', 'id_tasas_sala', 'id_logistica_grua'];
    var display;

    function formatEuro(value) {
        return '\u20AC' + value.toFixed(2);
    }

    function calculateTotal() {
        if (!display) return;
        var total = 0;
        for (var i = 0; i < fieldIds.length; i++) {
            var el = document.getElementById(fieldIds[i]);
            if (el) {
                var val = parseFloat(el.value);
                if (!isNaN(val)) total += val;
            }
        }
        display.textContent = formatEuro(total);
    }

    document.addEventListener('DOMContentLoaded', function () {
        display = document.getElementById('coste-inicial-display');
        if (!display) return;

        for (var i = 0; i < fieldIds.length; i++) {
            var el = document.getElementById(fieldIds[i]);
            if (el) {
                el.addEventListener('input', calculateTotal);
                el.addEventListener('change', calculateTotal);
            }
        }

        calculateTotal();
    });
})();
