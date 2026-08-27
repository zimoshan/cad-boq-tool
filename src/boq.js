function calculateBOQ(items) {
  // items: array of { name, quantity, unit, rate }
  if (!Array.isArray(items)) throw new TypeError('items must be an array');
  return items.map(it => ({
    name: it.name || 'unknown',
    quantity: Number(it.quantity) || 0,
    unit: it.unit || '',
    rate: Number(it.rate) || 0,
    total: (Number(it.quantity) || 0) * (Number(it.rate) || 0)
  }));
}

module.exports = { calculateBOQ };
