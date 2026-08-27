#!/usr/bin/env node
const { calculateBOQ } = require('./boq');

function main(argv = process.argv.slice(2)) {
  if (argv.length === 0) {
    console.log('cad-boq-tool — a BOQ calculation utility');
    console.log('Usage: cad-boq-tool <command>');
    console.log('Commands:');
    console.log('  demo    Run demo calculation');
    return;
  }
  const cmd = argv[0];
  if (cmd === 'demo') {
    const demoItems = [{ name: 'Wall', quantity: 10, unit: 'm2', rate: 50 }];
    const result = calculateBOQ(demoItems);
    console.log(JSON.stringify(result, null, 2));
  } else {
    console.error('Unknown command:', cmd);
    process.exitCode = 1;
  }
}

if (require.main === module) {
  main();
}

module.exports = { main };
