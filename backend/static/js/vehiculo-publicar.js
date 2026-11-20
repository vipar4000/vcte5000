/**
 * Publicar vehículo: gestión de las filas del formset de imágenes.
 *
 * - "Añadir foto" clona la plantilla oculta (#empty-form-template).
 * - "Quitar" en una foto ya guardada marca su checkbox DELETE (oculto) y
 *   esconde la fila; en una fila nueva la elimina del DOM y ajusta
 *   TOTAL_FORMS para que el formset no la espere.
 *
 * Al marcar DELETE el servidor borra el registro sin volver a leer el archivo,
 * así que funciona aunque la foto se perdiera en un despliegue.
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var contenedor = document.getElementById('filas-imagenes');
        var totalForms = document.getElementById('id_imagenes-TOTAL_FORMS');
        var botonAgregar = document.getElementById('btn-add-imagen');
        var plantilla = document.getElementById('empty-form-template');

        if (!contenedor) return;

        /* ── Añadir fila ─────────────────────────────────────────── */

        if (botonAgregar && totalForms && plantilla) {
            botonAgregar.addEventListener('click', function () {
                var indice = parseInt(totalForms.value, 10) || 0;
                var wrapper = document.createElement('div');
                wrapper.innerHTML = plantilla.innerHTML.replace(/__prefix__/g, indice);
                var fila = wrapper.firstElementChild;
                if (!fila) return;

                // Orden sugerido: el siguiente número libre
                var ordenInput = fila.querySelector('input[name$="-orden"]');
                if (ordenInput) {
                    var visibles = contenedor.querySelectorAll('.imagen-row').length;
                    ordenInput.value = visibles + 1;
                }

                contenedor.appendChild(fila);
                totalForms.value = indice + 1;
            });
        }

        /* ── Quitar fila ─────────────────────────────────────────── */

        contenedor.addEventListener('click', function (evento) {
            var boton = evento.target.closest('.btn-quitar-imagen');
            if (!boton) return;
            evento.preventDefault();

            var fila = boton.closest('.imagen-row');
            if (!fila) return;

            var eliminar = fila.querySelector('input[type="checkbox"][name$="-DELETE"]');
            if (eliminar) {
                // Foto ya guardada: se marca para borrar y se oculta la fila
                eliminar.checked = true;
                fila.style.display = 'none';
                return;
            }

            // Fila nueva (sin id): se quita del DOM y se ajusta el total
            fila.remove();
            if (totalForms) {
                var total = parseInt(totalForms.value, 10) || 0;
                if (total > 0) totalForms.value = total - 1;
            }
        });
    });
})();
