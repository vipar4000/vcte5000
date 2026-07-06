CREATE OR REPLACE FUNCTION prevent_factura_modificacion()
RETURNS TRIGGER AS $$
BEGIN
    -- Solo bloquear UPDATE/DELETE si contabilizada = true
    IF TG_OP = 'UPDATE' THEN
        IF OLD.contabilizada = true THEN
            RAISE EXCEPTION 'Factura % contabilizada. No se puede modificar (VeriFactu).',
                OLD.codigo_factura;
        END IF;
        -- Bloquear cambios en campos de integridad
        IF OLD.hash_verifactu IS NOT NULL AND OLD.hash_verifactu != NEW.hash_verifactu THEN
            RAISE EXCEPTION 'No se puede modificar el hash_verifactu de una factura.';
        END IF;
        IF OLD.precio_venta_total != NEW.precio_venta_total THEN
            RAISE EXCEPTION 'No se puede modificar el importe de una factura ya emitida.';
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        IF OLD.contabilizada = true THEN
            RAISE EXCEPTION 'Factura % contabilizada. No se puede eliminar (VeriFactu).',
                OLD.codigo_factura;
        END IF;
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_factura_inmutabilidad ON sales_facturaventa;

CREATE TRIGGER trg_factura_inmutabilidad
    BEFORE UPDATE OR DELETE ON sales_facturaventa
    FOR EACH ROW
    EXECUTE FUNCTION prevent_factura_modificacion();
