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