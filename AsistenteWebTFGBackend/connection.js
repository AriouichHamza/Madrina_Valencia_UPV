const mysql = require('mysql2');
//Importar -env
require('dotenv').config();

//for the server
/*const pool = mysql.createPool({
  host: process.env.DB_HOST,
  user: process.env.DB_USER,
  port: process.env.DB_PORT,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  waitForConnections: true
});*/

//for the tests
const pool = mysql.createPool({
  host: process.env.DB_HOST,
  user: process.env.DB_USER,
  port: '3306',
  password: process.env.DB_PASSWORD,
  database: 'MargotDB',
  waitForConnections: true
});
  
pool.on('connection', (stream) => {
  console.log('open pool', new Date());
})

pool.on('error', (err) => {
  if (err.code == 'PROTOCOL_CONNECTION_LOST') {
    console.log('\n\x1b[31mPROTOCOL_CONNECTION_LOST\nPéridida de conexión en la base de datos\x1b[0m');
  } else {
    console.log('\n\x1b[33merror en la conexión de la base de datos\x1b[0m');
  }
  console.log('Desconectado', new Date());
});

const isConnected = (callback) => {
  let sql = 'SELECT 1';
  let options = undefined;
  pool.getConnection(function (err, conn) {
    if (err) {
      callback(false);
    } else {
      conn.query(sql, options, function (err, results, fields) {
        if (err) { callback( false ); }
        else { callback( true ); }
      });
      conn.release();
    }
  });
}

const query = (sql, options, callback) => {

  pool.getConnection(function (err, conn) {
    if (err) {
      callback(err, null, null);
    } else {
      conn.query(sql, options, function (err, results, fields) {
        // Devolución de llamada impulsada por eventos
        callback(err, results, fields);
      });
      // Liberar la conexión, debe tenerse en cuenta que la liberación de la conexión debe liberarse aquí, no en la devolución de llamada de consulta
      conn.release();
    }
  });
};

const syncQuery = async (sql, options) => {

  // now get a Promise wrapped instance of that pool
  const promisePool = pool.promise();
  // query database using promises
  try {
    const [rows, fields] = await promisePool.query(sql, options); 
    return rows;
  } catch (err) {
    return undefined;
  }
}

module.exports.isConnected = isConnected;
module.exports.query = query;
module.exports.syncQuery = syncQuery;
