/**
 * Vehiculo imagenes: añadir/quitar imágenes adicionales dinamicamente.
 *
 * Maneja el formset inline de ImagenVehiculo con un prototipo oculto
 * y botones para añadir/quitar filas hasta un maximo de 8.
 */
(function () {
    'use strict';

    var MAX_IMAGES = 8;
    var totalFormsInput;
    var formsetContainer;
    var emptyTemplate;
    var addButton;
    var counterEl;

    function getRowCount() {
        if (!formsetContainer) return 0;
        return formsetContainer.querySelectorAll('.imagen-row').length;
    }

    function getVisibleCount() {
        if (!formsetContainer) return 0;
        var rows = formsetContainer.querySelectorAll('.imagen-row');
        var visible = 0;
        for (var i = 0; i < rows.length; i++) {
            if (rows[i].style.display !== 'none') visible++;
        }
        return visible;
    }

    function updateCounter() {
        var visible = getVisibleCount();
        if (counterEl) {
            counterEl.textContent = visible + ' de ' + MAX_IMAGES + ' imagenes';
        }
        if (addButton) {
            addButton.style.display = visible >= MAX_IMAGES ? 'none' : '';
        }
    }

    function removeRow(row) {
        var deleteCheckbox = row.querySelector('[id$="-DELETE"]');
        if (deleteCheckbox) {
            deleteCheckbox.checked = true;
            row.style.display = 'none';
        } else {
            row.remove();
        }
        updateCounter();
    }

    function addRow() {
        if (!totalFormsInput || !formsetContainer || !emptyTemplate) return;

        var currentTotal = parseInt(totalFormsInput.value, 10);
        if (currentTotal >= MAX_IMAGES) return;

        var html = emptyTemplate.innerHTML.replace(/__prefix__/g, currentTotal);
        var div = document.createElement('div');
        div.innerHTML = html;
        var row = div.firstElementChild;

        // Set orden field based on visible count
        var ordenInput = row.querySelector('[id$="-orden"]');
        if (ordenInput) {
            ordenInput.value = getVisibleCount() + 1;
        }

        formsetContainer.appendChild(row);
        totalFormsInput.value = currentTotal + 1;

        // Bind remove to new row
        var removeBtn = row.querySelector('.btn-quitar-imagen');
        if (removeBtn) {
            removeBtn.addEventListener('click', function () {
                removeRow(row);
            });
        }

        updateCounter();
    }

    document.addEventListener('DOMContentLoaded', function () {
        totalFormsInput = document.getElementById('id_imagenes-TOTAL_FORMS');
        formsetContainer = document.getElementById('imagenes-formset-rows');
        emptyTemplate = document.getElementById('empty-form-template');
        addButton = document.getElementById('add-imagen-btn');
        counterEl = document.getElementById('imagenes-counter');

        if (!formsetContainer) return;

        // Bind remove to existing rows
        var existingRows = formsetContainer.querySelectorAll('.imagen-row');
        for (var i = 0; i < existingRows.length; i++) {
            var btn = existingRows[i].querySelector('.btn-quitar-imagen');
            if (btn) {
                btn.addEventListener('click', (function (row) {
                    return function () { removeRow(row); };
                })(existingRows[i]));
            }
        }

        // Bind add button
        if (addButton) {
            addButton.addEventListener('click', addRow);
        }

        updateCounter();
    });
})();
