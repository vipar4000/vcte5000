from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Sum, Count, F
from datetime import datetime, timedelta
from .models import Marcaje, ConfiguracionNomina
from .forms import MarcajeForm, PinMarcajeForm, ConfiguracionNominaForm
from apps.accounts.models import User


@login_required
def marcaje_list(request):
    """Lista de marcajes con filtros."""
    marcajes = Marcaje.objects.select_related('operario').all()
    
    # Filtros
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    operario_id = request.GET.get('operario', '')
    
    if fecha_desde:
        marcajes = marcajes.filter(fecha_hora__date__gte=fecha_desde)
    
    if fecha_hasta:
        marcajes = marcajes.filter(fecha_hora__date__lte=fecha_hasta)
    
    if operario_id:
        marcajes = marcajes.filter(operario_id=operario_id)
    
    # Estadísticas del día
    hoy = timezone.now().date()
    marcajes_hoy = Marcaje.objects.filter(fecha_hora__date=hoy)
    
    stats = {
        'total_hoy': marcajes_hoy.count(),
        'entradas_hoy': marcajes_hoy.filter(tipo='ENTRADA').count(),
        'operarios_presentes': marcajes_hoy.filter(tipo='ENTRADA').values('operario').distinct().count(),
    }
    
    operarios = User.objects.filter(rol='OPERARIO', is_active=True)
    
    context = {
        'marcajes': marcajes[:100],
        'stats': stats,
        'operarios': operarios,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'is_admin': request.user.is_admin,
    }
    return render(request, 'attendance/list.html', context)


@login_required
def marcaje_create(request):
    """Crear un nuevo marcaje manual."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para crear marcajes.')
        return redirect('attendance:marcajes')
    
    if request.method == 'POST':
        form = MarcajeForm(request.POST)
        if form.is_valid():
            marcaje = form.save(commit=False)
            marcaje.fecha_hora = timezone.now()
            marcaje.ip_address = get_client_ip(request)
            marcaje.validado = True
            marcaje.save()
            messages.success(
                request, 
                f'Marcaje registrado: {marcaje.get_tipo_display()} - {marcaje.operario.get_full_name}'
            )
            return redirect('attendance:marcajes')
    else:
        form = MarcajeForm()
    
    context = {
        'form': form,
    }
    return render(request, 'attendance/form.html', context)


@login_required
def kiosco_view(request):
    """Vista kiosco para tablets - fichaje por PIN."""
    form = PinMarcajeForm()
    mensaje = None
    tipo_mensaje = None
    
    if request.method == 'POST':
        form = PinMarcajeForm(request.POST)
        if form.is_valid():
            pin = form.cleaned_data['pin']
            
            # Buscar operario por PIN
            try:
                operario = User.objects.get(pin_kiosco=pin, rol='OPERARIO', is_active=True)
                
                # Verificar geofencing
                ip_address = get_client_ip(request)
                if not verificar_geofencing(ip_address):
                    mensaje = '❌ Acceso denegado: fuera de la zona permitida'
                    tipo_mensaje = 'error'
                else:
                    # Determinar tipo de marcaje
                    ultimo_marcaje = Marcaje.objects.filter(
                        operario=operario
                    ).order_by('-fecha_hora').first()
                    
                    if ultimo_marcaje and ultimo_marcaje.tipo == 'ENTRADA':
                        tipo = 'SALIDA'
                    else:
                        tipo = 'ENTRADA'
                    
                    # Crear marcaje
                    marcaje = Marcaje.objects.create(
                        operario=operario,
                        tipo=tipo,
                        fecha_hora=timezone.now(),
                        ip_address=ip_address,
                        validado=True,
                    )
                    
                    mensaje = f'✅ {operario.get_full_name()} - {tipo}'
                    tipo_mensaje = 'success'
                    
            except User.DoesNotExist:
                mensaje = '❌ PIN no válido'
                tipo_mensaje = 'error'
    
    context = {
        'form': form,
        'mensaje': mensaje,
        'tipo_mensaje': tipo_mensaje,
    }
    return render(request, 'attendance/kiosco.html', context)


@login_required
def configuracion_nomina_list(request):
    """Lista de configuraciones de nómina."""
    configuraciones = ConfiguracionNomina.objects.select_related('operario').all()
    
    context = {
        'configuraciones': configuraciones,
        'is_admin': request.user.is_admin,
    }
    return render(request, 'attendance/nomina_list.html', context)


@login_required
def configuracion_nomina_create(request):
    """Crear configuración de nómina."""
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para configurar nóminas.')
        return redirect('attendance:nomina_list')
    
    if request.method == 'POST':
        form = ConfiguracionNominaForm(request.POST)
        if form.is_valid():
            config = form.save()
            
            # Actualizar salario en el modelo User
            operario = config.operario
            operario.salario_base_mensual = config.salario_base_mensual
            operario.porcentaje_ss_patronal = config.porcentaje_ss_patronal
            operario.save()
            
            messages.success(
                request, 
                f'Nómina configurada para {operario.get_full_name()}'
            )
            return redirect('attendance:nomina_list')
    else:
        form = ConfiguracionNominaForm()
    
    context = {
        'form': form,
    }
    return render(request, 'attendance/nomina_form.html', context)


@login_required
def configuracion_nomina_update(request, pk):
    """Actualizar configuración de nómina."""
    config = get_object_or_404(ConfiguracionNomina, pk=pk)
    
    if not request.user.is_admin:
        messages.error(request, 'No tiene permisos para editar nóminas.')
        return redirect('attendance:nomina_list')
    
    if request.method == 'POST':
        form = ConfiguracionNominaForm(request.POST, instance=config)
        if form.is_valid():
            config = form.save()
            
            # Actualizar salario en el modelo User
            operario = config.operario
            operario.salario_base_mensual = config.salario_base_mensual
            operario.porcentaje_ss_patronal = config.porcentaje_ss_patronal
            operario.save()
            
            messages.success(
                request, 
                f'Nómina actualizada para {operario.get_full_name()}'
            )
            return redirect('attendance:nomina_list')
    else:
        form = ConfiguracionNominaForm(instance=config)
    
    context = {
        'form': form,
        'config': config,
    }
    return render(request, 'attendance/nomina_form.html', context)


@login_required
def reporte_jornada(request, operario_id):
    """Reporte de jornada laboral por operario."""
    operario = get_object_or_404(User, pk=operario_id, rol='OPERARIO')
    
    # Obtener marcajes del mes actual
    hoy = timezone.now().date()
    primer_dia_mes = hoy.replace(day=1)
    
    marcajes = Marcaje.objects.filter(
        operario=operario,
        fecha_hora__date__gte=primer_dia_mes,
        fecha_hora__date__lte=hoy
    ).order_by('fecha_hora')
    
    # Calcular horas trabajadas por día
    jornadas = {}
    for marcaje in marcajes:
        fecha = marcaje.fecha_hora.date()
        if fecha not in jornadas:
            jornadas[fecha] = {'entradas': [], 'salidas': []}
        
        if marcaje.tipo == 'ENTRADA':
            jornadas[fecha]['entradas'].append(marcaje.fecha_hora)
        elif marcaje.tipo == 'SALIDA':
            jornadas[fecha]['salidas'].append(marcaje.fecha_hora)
    
    # Calcular horas totales
    horas_totales = 0
    for fecha, datos in jornadas.items():
        if datos['entradas'] and datos['salidas']:
            entrada = min(datos['entradas'])
            salida = max(datos['salidas'])
            horas = (salida - entrada).total_seconds() / 3600
            horas_totales += horas
    
    # Obtener configuración de nómina
    try:
        config_nomina = ConfiguracionNomina.objects.get(operario=operario)
        coste_hora = config_nomina.coste_hora
    except ConfiguracionNomina.DoesNotExist:
        config_nomina = None
        coste_hora = 0
    
    context = {
        'operario': operario,
        'marcajes': marcajes,
        'jornadas': jornadas,
        'horas_totales': horas_totales,
        'coste_hora': coste_hora,
        'coste_total': horas_totales * coste_hora,
        'config_nomina': config_nomina,
        'mes_actual': hoy.strftime('%B %Y'),
    }
    return render(request, 'attendance/reporte_jornada.html', context)


def verificar_geofencing(ip_address):
    """
    Verifica si la IP está en la red permitida del galpón.
    En producción, esto verificaría contra las IPs del router 5G.
    """
    # IPs permitidas (configurar según la red del galpón)
    ips_permitidas = [
        '127.0.0.1',
        'localhost',
        '192.168.1.',  # Red local del galpón
        '10.0.0.',     # Red alternativa
    ]
    
    for ip in ips_permitidas:
        if ip_address.startswith(ip):
            return True
    
    return False


def get_client_ip(request):
    """Obtiene la IP del cliente."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
