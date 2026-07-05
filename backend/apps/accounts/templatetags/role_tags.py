from django import template

register = template.Library()


@register.simple_tag
def has_role(user, role):
    """Verifica si el usuario tiene un rol específico."""
    if user.is_authenticated:
        return user.rol == role
    return False


@register.simple_tag
def is_admin(user):
    """Verifica si el usuario es administrador."""
    if user.is_authenticated:
        return user.is_admin
    return False


@register.simple_tag
def is_operario(user):
    """Verifica si el usuario es operario."""
    if user.is_authenticated:
        return user.is_operario
    return False


@register.simple_tag
def is_vendedor(user):
    """Verifica si el usuario es vendedor."""
    if user.is_authenticated:
        return user.is_vendedor
    return False


@register.simple_tag
def is_gestoria(user):
    """Verifica si el usuario es de gestoría."""
    if user.is_authenticated:
        return user.is_gestoria
    return False
