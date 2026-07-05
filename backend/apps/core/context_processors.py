def user_roles_context(request):
    """Context processor that adds user role flags to all templates."""
    if request.user.is_authenticated:
        return {
            'is_admin': request.user.is_admin,
            'is_operario': request.user.rol == 'OPERARIO',
            'is_vendedor': request.user.rol == 'VENDEDOR',
            'is_gestoria': request.user.rol == 'GESTORIA',
        }
    return {
        'is_admin': False,
        'is_operario': False,
        'is_vendedor': False,
        'is_gestoria': False,
    }
