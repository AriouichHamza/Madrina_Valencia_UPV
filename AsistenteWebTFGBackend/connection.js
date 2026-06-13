const mysql = require('mysql2');
require('dotenv').config();

// Connection pool — all database variables come from environment variables or
// fall back to safe defaults.
const pool = mysql.createPool({
  host: process.env.DB_HOST || '127.0.0.1',
  user: process.env.DB_USER || 'root',
  port: Number(process.env.DB_PORT || 3306),
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME || 'MargotDB',
  waitForConnections: true,
  connectionLimit: Number(process.env.DB_CONNECTION_LIMIT || 10),
});

pool.on('connection', (stream) => {
  console.log('Pool connection opened', new Date());
})

pool.on('error', (err) => {
  if (err.code == 'PROTOCOL_CONNECTION_LOST') {
    console.log('\n\x1b[31mPROTOCOL_CONNECTION_LOST\nDatabase connection was lost\x1b[0m');
  } else {
    console.log('\n\x1b[33mDatabase connection error\x1b[0m');
  }
  console.log('Disconnected', new Date());
});

// Runs a lightweight SELECT 1 to verify the pool can reach the database.
const isConnected = (callback) => {
  let sql = 'SELECT 1';
  let options = undefined;
  pool.getConnection(function (err, conn) {
    if (err) {
      callback(false, err);
    } else {
      conn.query(sql, options, function (err, results, fields) {
        if (err) { callback(false, err); }
        else { callback(true, null); }
        conn.release();
      });
    }
  });
}

const query = (sql, options, callback) => {
  pool.getConnection(function (err, conn) {
    if (err) {
      callback(err, null, null);
    } else {
      conn.query(sql, options, function (err, results, fields) {
        // Event-driven callback — release the connection here, not inside the query callback.
        callback(err, results, fields);
      });
      conn.release();
    }
  });
};

const syncQuery = async (sql, options) => {
  // Get a Promise-wrapped instance of the pool.
  const promisePool = pool.promise();
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
