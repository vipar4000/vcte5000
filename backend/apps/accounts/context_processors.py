def user_roles(request):
    """Context processor para información de roles del usuario."""
    context = {
        'is_admin': False,
        'is_operario': False,
        'is_vendedor': False,
        'is_gestoria': False,
    }
    
    if request.user.is_authenticated:
        context['is_admin'] = request.user.is_admin
        context['is_operario'] = request.user.is_operario
        context['is_vendedor'] = request.user.is_vendedor
        context['is_gestoria'] = request.user.is_gestoria
    
    return context
