import { runMigrations } from './pool.js';

runMigrations()
  .then(() => {
    console.log('Migrations complete.');
    process.exit(0);
  })
  .catch((error) => {
    console.error('Migration failed:', error);
    process.exit(1);
  });
