// Healthcheck del container: verifica che il server HTTP risponda sulla 8000.
const r = await fetch('http://127.0.0.1:8000/');
if (!r.ok) Deno.exit(1);
console.log('healthcheck ok');
