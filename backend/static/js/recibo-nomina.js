/**
 * Recibo de nómina: abre el diálogo de impresión del navegador.
 *
 * Se hace desde un archivo externo (no `onclick`) porque la política CSP del
 * ERP bloquea el JavaScript en línea.
 */
document.addEventListener('DOMContentLoaded', function () {
    var boton = document.getElementById('btn-imprimir-recibo');
    if (!boton) {
        return;
    }

    boton.addEventListener('click', function (evento) {
        evento.preventDefault();
        window.print();
    });
});
