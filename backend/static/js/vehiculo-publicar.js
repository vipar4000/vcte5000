/**
 * Publicar vehículo: añadir filas al formset de imágenes.
 *
 * El bloque de plantilla (#empty-form-template) trae el formulario vacío con el
 * prefijo "__prefix__"; al pulsar "Añadir foto" se clona con el índice actual.
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var contenedor = document.getElementById('filas-imagenes');
        var totalForms = document.getElementById('id_imagenes-TOTAL_FORMS');
        var boton = document.getElementById('btn-add-imagen');
        var plantilla = document.getElementById('empty-form-template');

        if (!contenedor || !totalForms || !boton || !plantilla) return;

        boton.addEventListener('click', function () {
            var indice = parseInt(totalForms.value, 10);
            var wrapper = document.createElement('div');
            wrapper.innerHTML = plantilla.innerHTML.replace(/__prefix__/g, indice);
            var fila = wrapper.firstElementChild;
            if (!fila) return;
            contenedor.appendChild(fila);
            totalForms.value = indice + 1;
        });
    });
})();
