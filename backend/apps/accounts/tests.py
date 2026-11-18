"""Gestión de usuarios dentro del ERP (/erp/usuarios/)."""
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User


class GestionUsuariosTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin', email='admin@eurocar.local',
            password='admin123!', rol='ADMIN',
        )
        self.operario = User.objects.create_user(
            username='mecanico1', email='m1@eurocar.local',
            password='mecanico123!', rol='OPERARIO',
        )
        self.client.force_login(self.admin)

    def _datos(self, **extra):
        datos = {
            'username': 'vendedor2',
            'first_name': 'Ana',
            'last_name': 'Lopez',
            'email': 'v2@eurocar.local',
            'movil': '',
            'rol': 'VENDEDOR',
            'pin_kiosco': '',
            'is_active': 'on',
            'puede_eliminar': 'on',
            'salario_base_mensual': '',
            'porcentaje_ss_patronal': '31.50',
            'password': '',
            'password2': '',
        }
        datos.update(extra)
        return datos

    # ------------------------------------------------------------- listado
    def test_admin_ve_el_listado(self):
        response = self.client.get(reverse('usuarios:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'mecanico1')

    def test_no_admin_no_puede_entrar(self):
        self.client.force_login(self.operario)
        response = self.client.get(reverse('usuarios:list'))
        self.assertRedirects(response, reverse('home'))

    def test_buscador_filtra(self):
        response = self.client.get(reverse('usuarios:list'), {'busqueda': 'mecanico'})
        self.assertContains(response, 'mecanico1')
        self.assertNotContains(response, 'admin@eurocar.local')

    # --------------------------------------------------------------- alta
    def test_crear_usuario_con_contrasena(self):
        response = self.client.post(
            reverse('usuarios:create'),
            self._datos(password='claveSegura123', password2='claveSegura123'),
        )
        self.assertEqual(response.status_code, 302)
        usuario = User.objects.get(username='vendedor2')
        self.assertTrue(usuario.check_password('claveSegura123'))
        self.assertEqual(usuario.rol, 'VENDEDOR')

    def test_crear_exige_contrasena(self):
        response = self.client.post(reverse('usuarios:create'), self._datos())
        self.assertEqual(response.status_code, 200)  # se vuelve a mostrar el formulario
        self.assertFalse(User.objects.filter(username='vendedor2').exists())

    def test_rechaza_pin_no_numerico(self):
        response = self.client.post(
            reverse('usuarios:create'),
            self._datos(pin_kiosco='12a4', password='claveSegura123', password2='claveSegura123'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='vendedor2').exists())

    # ------------------------------------------------------------ edicion
    def test_editar_sin_contrasena_no_la_cambia(self):
        response = self.client.post(
            reverse('usuarios:update', args=[self.operario.pk]),
            self._datos(username='mecanico1', email='m1@eurocar.local', rol='OPERARIO'),
        )
        self.assertEqual(response.status_code, 302)
        self.operario.refresh_from_db()
        self.assertTrue(self.operario.check_password('mecanico123!'))

    def test_editar_con_contrasena_la_cambia(self):
        response = self.client.post(
            reverse('usuarios:update', args=[self.operario.pk]),
            self._datos(
                username='mecanico1', email='m1@eurocar.local', rol='OPERARIO',
                password='otraClave123', password2='otraClave123',
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.operario.refresh_from_db()
        self.assertTrue(self.operario.check_password('otraClave123'))

    # ---------------------------------------------------- activar/desactivar
    def test_desactivar_y_activar(self):
        self.client.post(reverse('usuarios:toggle', args=[self.operario.pk]))
        self.operario.refresh_from_db()
        self.assertFalse(self.operario.is_active)

        self.client.post(reverse('usuarios:toggle', args=[self.operario.pk]))
        self.operario.refresh_from_db()
        self.assertTrue(self.operario.is_active)

    def test_no_puede_desactivarse_a_si_mismo(self):
        self.client.post(reverse('usuarios:toggle', args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_toggle_solo_por_post(self):
        response = self.client.get(reverse('usuarios:toggle', args=[self.operario.pk]))
        self.assertEqual(response.status_code, 302)
        self.operario.refresh_from_db()
        self.assertTrue(self.operario.is_active)

    # ------------------------------------------------------------ desbloqueo
    def test_desbloquear_cuenta(self):
        self.operario.lock_account()
        self.assertTrue(self.operario.is_locked)

        self.client.post(reverse('usuarios:unlock', args=[self.operario.pk]))

        self.operario.refresh_from_db()
        self.assertFalse(self.operario.is_locked)
        self.assertEqual(self.operario.failed_login_attempts, 0)
