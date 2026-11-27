/* «Guardar y registrar otro» sin salir de la página.
 *
 * Envía el formulario de alta de vehículo por fetch y, si todo va bien,
 * limpia el formulario y deja el foco en la matrícula para el siguiente
 * coche. Sin JavaScript, el botón sigue funcionando con el envío normal.
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var boton = document.querySelector('button[name="guardar_y_otro"]');
        if (!boton) return;

        var formulario = boton.form;
        if (!formulario) return;

        var aviso = document.getElementById('aviso-guardar-otro');
        var contador = document.getElementById('contador-guardar-otro');
        var registrados = 0;

        function mostrar(mensaje, esError) {
            if (!aviso) return;
            aviso.textContent = mensaje;
            aviso.className = esError
                ? 'mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800'
                : 'mb-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800';
            aviso.classList.remove('hidden');
            if (contador) {
                if (registrados > 0) {
                    contador.textContent = registrados + (
                        registrados === 1
                            ? ' vehículo registrado en esta sesión'
                            : ' vehículos registrados en esta sesión'
                    );
                    contador.classList.remove('hidden');
                } else {
                    contador.classList.add('hidden');
                }
            }
        }

        function limpiarFormulario() {
            formulario.reset();
            // Los <input type="file"> no se limpian con reset() en algunos navegadores
            var ficheros = formulario.querySelectorAll('input[type="file"]');
            for (var i = 0; i < ficheros.length; i++) {
                ficheros[i].value = '';
            }
            var matricula = formulario.querySelector(
                'input[name="matricula"], #id_matricula'
            );
            if (matricula) {
                matricula.focus();
                matricula.scrollIntoView({ block: 'center', behavior: 'smooth' });
            }
        }

        function erroresDe(datos) {
            if (!datos || !datos.errores) return 'Revise los datos del formulario.';
            var partes = [];
            for (var campo in datos.errores) {
                if (!Object.prototype.hasOwnProperty.call(datos.errores, campo)) {
                    continue;
                }
                var lista = datos.errores[campo];
                var texto = Array.isArray(lista) ? lista.join(' ') : String(lista);
                partes.push(campo + ': ' + texto);
            }
            return partes.length ? partes.join(' · ') : 'Revise los datos del formulario.';
        }

        boton.addEventListener('click', function (evento) {
            evento.preventDefault();

            if (boton.disabled) return;
            boton.disabled = true;
            var textoOriginal = boton.textContent;
            boton.textContent = 'Guardando…';

            var datos = new FormData(formulario);
            datos.append('guardar_y_otro', '1');

            fetch(formulario.action || window.location.href, {
                method: 'POST',
                body: datos,
                credentials: 'same-origin',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
                .then(function (respuesta) {
                    return respuesta.json().catch(function () {
                        return { ok: false, errores: {} };
                    });
                })
                .then(function (json) {
                    if (json && json.ok) {
                        registrados += 1;
                        mostrar(
                            (json.matricula ? json.matricula + ' registrado. ' : '') +
                            'Formulario listo para el siguiente vehículo.'
                        );
                        limpiarFormulario();
                    } else {
                        mostrar(erroresDe(json), true);
                    }
                })
                .catch(function () {
                    mostrar(
                        'No se pudo guardar el vehículo. Compruebe la conexión ' +
                        'e inténtelo de nuevo.', true
                    );
                })
                .then(function () {
                    boton.disabled = false;
                    boton.textContent = textoOriginal;
                });
        });
    });
})();
