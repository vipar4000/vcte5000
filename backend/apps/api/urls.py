from django.urls import path
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.db.models import Q
from django.utils import timezone
from apps.vehicles.models import Vehiculo, ImagenVehiculo
from apps.sales.models import VentaVehiculo


def is_html_request(request):
    """Detecta si el cliente quiere HTML."""
    # 1. Check Accept header (browser default)
    accept = request.META.get('HTTP_ACCEPT', '')
    if 'text/html' in accept:
        return True
    # 2. Check format parameter
    if request.GET.get('format') == 'html':
        return True
    return False


def api_health(request):
    """Health check endpoint."""
    data = {'status': 'ok', 'service': 'eurocar-erp'}
    
    if is_html_request(request):
        context = {
            'service': 'eurocar-erp',
            'fecha': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        return render(request, 'api/health.html', context)
    
    return JsonResponse(data)


def api_ping(request):
    """Lightweight health check for uptime monitoring (UptimeRobot)."""
    return HttpResponse("OK", content_type="text/plain", status=200)


def api_vehiculos_public(request):
    """API pública para listar vehículos en venta."""
    vehiculos = Vehiculo.objects.filter(
        estado='EN_VENTA',
        precio_venta__gt=0
    ).values(
        'id', 'marca', 'modelo', 'anio', 'kilometraje', 
        'combustible', 'etiqueta_ambiental', 'imagen_principal',
        'precio_venta', 'descripcion_dano', 'tipo_dano'
    )
    
    # Agregar URL de imagen principal e imágenes adicionales
    vehiculos_list = []
    for v in vehiculos:
        vehiculo_data = dict(v)
        # Agregar URLs de imágenes adicionales
        imagenes_adicionales = list(
            ImagenVehiculo.objects.filter(vehiculo_id=v['id'])
            .order_by('orden')
            .values_list('imagen', flat=True)
        )
        if vehiculo_data['imagen_principal']:
            vehiculo_data['imagen_url'] = f"/media/{vehiculo_data['imagen_principal']}"
        elif imagenes_adicionales:
            vehiculo_data['imagen_url'] = f"/media/{imagenes_adicionales[0]}"
        else:
            vehiculo_data['imagen_url'] = None
        vehiculos_list.append(vehiculo_data)
    
    # Filtros
    busqueda = request.GET.get('busqueda', '')
    marca = request.GET.get('marca', '')
    precio_min = request.GET.get('precio_min', '')
    precio_max = request.GET.get('precio_max', '')
    etiqueta = request.GET.get('etiqueta', '')
    
    filtros = []
    
    if busqueda:
        vehiculos_list = [
            v for v in vehiculos_list
            if busqueda.lower() in v['marca'].lower() or busqueda.lower() in v['modelo'].lower()
        ]
        filtros.append(f"Búsqueda: {busqueda}")
    
    if marca:
        vehiculos_list = [v for v in vehiculos_list if v['marca'].lower() == marca.lower()]
        filtros.append(f"Marca: {marca}")
    
    if etiqueta:
        vehiculos_list = [v for v in vehiculos_list if v['etiqueta_ambiental'] == etiqueta]
        filtros.append(f"Etiqueta: {etiqueta}")
    
    if precio_min:
        try:
            precio_min = float(precio_min)
            vehiculos_list = [v for v in vehiculos_list if v['precio_venta'] >= precio_min]
            filtros.append(f"Precio mín: {precio_min}€")
        except (ValueError, TypeError):
            pass
    
    if precio_max:
        try:
            precio_max = float(precio_max)
            vehiculos_list = [v for v in vehiculos_list if v['precio_venta'] <= precio_max]
            filtros.append(f"Precio máx: {precio_max}€")
        except (ValueError, TypeError):
            pass
    
    if is_html_request(request):
        context = {
            'vehiculos': vehiculos_list[:20],
            'total': len(vehiculos_list),
            'filtros': filtros,
            'fecha': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        return render(request, 'api/vehiculos_list.html', context)
    
    return JsonResponse({
        'vehiculos': vehiculos_list[:20],
        'total': len(vehiculos_list),
    })


def api_vehiculo_detalle(request, pk):
    """API pública para detalle de un vehículo."""
    try:
        vehiculo = Vehiculo.objects.get(pk=pk)
        imagen_url = None
        if vehiculo.imagen_principal:
            imagen_url = f"/media/{vehiculo.imagen_principal}"
        
        # Imágenes adicionales
        imagenes = []
        for img in vehiculo.imagenes.all().order_by('orden'):
            imagenes.append({
                'url': f"/media/{img.imagen}",
                'es_principal': img.es_principal,
                'orden': img.orden,
            })
        
        data = {
            'id': vehiculo.pk,
            'marca': vehiculo.marca,
            'modelo': vehiculo.modelo,
            'anio': vehiculo.anio,
            'kilometraje': vehiculo.kilometraje,
            'combustible': vehiculo.get_combustible_display(),
            'tipo_dano': vehiculo.get_tipo_dano_display(),
            'etiqueta_ambiental': vehiculo.get_etiqueta_ambiental_display(),
            'descripcion_dano': vehiculo.descripcion_dano,
            'imagen': imagen_url,
            'imagenes': imagenes,
            'precio_venta': float(vehiculo.precio_venta),
        }
        
        if is_html_request(request):
            context = {
                'vehiculo': data,
                'fecha': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            return render(request, 'api/vehiculo_detail.html', context)
        
        return JsonResponse(data)
    except Vehiculo.DoesNotExist:
        if is_html_request(request):
            context = {
                'error': 'Vehículo no encontrado',
                'fecha': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            return render(request, 'api/vehiculo_detail.html', context, status=404)
        return JsonResponse({'error': 'Vehículo no encontrado'}, status=404)


def api_marcas(request):
    """API pública para listar marcas disponibles."""
    marcas = Vehiculo.objects.filter(
        estado='EN_VENTA',
        precio_venta__gt=0
    ).values_list('marca', flat=True).distinct().order_by('marca')
    
    marcas_list = list(marcas)
    
    if is_html_request(request):
        context = {
            'marcas': marcas_list,
            'total': len(marcas_list),
            'fecha': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        return render(request, 'api/marcas_list.html', context)
    
    return JsonResponse({'marcas': marcas_list})


urlpatterns = [
    path('health/', api_health, name='health'),
    path('ping/', api_ping, name='ping'),
    path('vehiculos/', api_vehiculos_public, name='api_vehiculos'),
    path('vehiculos/<int:pk>/', api_vehiculo_detalle, name='api_vehiculo_detalle'),
    path('marcas/', api_marcas, name='api_marcas'),
]
