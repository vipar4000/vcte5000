/**
 * Formatea un numero como moneda EUR: 1.800,00 EUR
 * Punto para miles, coma para decimales, 2 decimales.
 */
export function formatEUR(value) {
  const num = Number(value)
  if (isNaN(num)) return '0,00 EUR'

  const parts = num.toFixed(2).split('.')
  const intPart = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  return intPart + ',' + parts[1] + ' EUR'
}

/**
 * Formatea un kilometraje con separador de miles: 95000 -> "95.000 km"
 */
export function formatKm(value) {
  const num = Number(value)
  if (isNaN(num)) return '0 km'

  const entero = Math.round(num).toString()
  return entero.replace(/\B(?=(\d{3})+(?!\d))/g, '.') + ' km'
}
