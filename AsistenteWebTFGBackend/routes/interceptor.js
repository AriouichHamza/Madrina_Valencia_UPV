var express = require('express');
var router = express.Router();

var db = require('../connection');

function err(message) {
  return { ok: false, data: {}, message: message }
}

// Session guard — every POST to /api must carry a valid session id and token.
// Matching the pair against the usuarios table prevents forged requests.
router.post('*', async (req, res, next) => {

  let usuario = req.body.session;

  let sql = 'SELECT * FROM usuarios WHERE id = ? AND token = ?';
  let rows = await db.syncQuery(sql, [usuario.id, usuario.token]);

  if (rows && rows.length == 1) {
    next();
  } else {
    res.send(err('Error de autenticación'));
  }
});

module.exports = router;
