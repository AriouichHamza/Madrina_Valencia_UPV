var CryptoJS = require('crypto-js');
var express = require('express');
var fs = require('fs');
var path = require('path');
var router = express.Router();
var db = require('../connection');

const { exec } = require("child_process");

const MAIL_CONFIG = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'mail', 'config.json'), 'utf8'));
const MAIL = fs.readFileSync(path.join(__dirname, '..', 'mail', 'mail.html'), 'utf8');
const SECRET_KEY = '>%+C|{JTblF(Xbn';

function ok(data) {
  return { ok: true, data: data, message: '' };
}

function err(message) {
  return { ok: false, data: {}, message: message }
}

function encryptPassword(id, password) {
  return CryptoJS.SHA3(id + SECRET_KEY + password, { outputLength: 256 }).toString();
}

function encryptEmail(email) {
  return CryptoJS.SHA3(SECRET_KEY + email, { outputLength: 256 }).toString();
}

function getMailBody(id, token) {
  let body = MAIL;
  body = body.replaceAll('$userID$', id);
  body = body.replaceAll('$domain$', MAIL_CONFIG.domain);
  return body.replaceAll('$token$', token);
}

function sendMailCommand(cuerpo, asunto, destino) {
  return `echo "${cuerpo}" | mail -a "Content-type: text/html" -s "${asunto}" -r noreply@disca.upv.es ${destino}`;
}

async function randomId() {

  let id = 0, rows = [];
  do {
    id = randomToken(24);
    rows = await db.syncQuery('SELECT * FROM usuarios WHERE id = ?', [id]);
  } while (rows.length > 0);
  return id;
}

function randomToken(max) {
  let length = max;
  let result = '';
  let characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let charactersLength = characters.length;
  for (let i = 0; i < length; i++) {
    result += characters.charAt(Math.floor(Math.random() * charactersLength));
  }
  return result;
}

router.post('/insert', async (req, res) => {

  let usuario = req.body;

  usuario.nombre = usuario.nombre.trim();
  usuario.correo = usuario.correo.trim();
  usuario.password = usuario.password.trim();

  let sql = 'SELECT nombre FROM usuarios WHERE nombre = ?';
  let rows = await db.syncQuery(sql, [usuario.nombre]);

  sql = 'SELECT correo FROM usuarios WHERE correo = ?';
  rowsCorreo = await db.syncQuery(sql, [encryptEmail(usuario.correo)]);

  if (rows || rowsCorreo) {
    if (rows.length > 0 || rowsCorreo.length > 0) {

      if (rows.length > 0 && rowsCorreo.length == 0) res.send(err('El nombre del usuario ya está en uso'));
      else if (rowsCorreo.length > 0 && rows.length == 0) res.send(err('El correo electrónico ya está en uso'));
      else res.send(err('El nombre de usuario  y el correo electrónico ya están en uso'));

    } else {

      let id = await randomId();
      let correo = encryptEmail(usuario.correo);
      let nombre = usuario.nombre.toLowerCase();
      let password = encryptPassword(id, usuario.password);

      let perf = [id, false, 'utf8', ';']
      let sql2 = 'INSERT INTO preferencias (id, cabecera, encode, sep) VALUES (?, ?, ?, ?)';
      db.query(sql2, perf, (error, rows, fields) => { });

      let u = [id, correo, nombre, password, ''];
      let sql1 = 'INSERT INTO usuarios (id, correo, nombre, password, token) VALUES (?, ?, ?, ?, ?)';
      db.query(sql1, u, (error, rows, fields) => {
        if (error) { res.send(err('Fallo al guardar el nuevo usuario')); }
        else { res.send(ok('Usuario registrado')); }
      });
    }

  } else {
    res.send(err('Fallo al comprobar el nombre'));
  }
});

router.post('/select', async (req, res) => {

  let usuario = req.body;

  usuario.nombre = usuario.nombre.trim().toLowerCase();

  let sql = 'SELECT id FROM usuarios WHERE nombre = ?';
  let args = [usuario.nombre];
  let rows = await db.syncQuery(sql, args);

  if (!rows) { res.send(err('Fallo al buscar el usuario en la base de datos')); return; }
  if (rows.length != 1) { res.send(err('El usuario no existe')); return; }

  sql = 'SELECT * FROM usuarios WHERE nombre = ? AND password = ?';
  args = [usuario.nombre, encryptPassword(rows[0].id, usuario.password)];
  rows = await db.syncQuery(sql, args);

  if (!rows) { res.send(err('Fallo al buscar el usuario en la base de datos')); return; }
  if (rows.length != 1) { res.send(err('Contraseña incorrecta')); return; }

  let token = '';
  do {
    token = randomToken(64);
    tokens = await db.syncQuery('SELECT * FROM usuarios WHERE token = ?', [token]);
  } while (tokens.length > 0);

  let u = { id: rows[0].id, nombre: rows[0].nombre, token: token };

  let update = 'UPDATE usuarios SET token = ? WHERE id = ?';
  db.query(update, [token, u.id], (error, rows, fields) => { });

  res.send(ok(u));
});

router.post('/delete', (req, res) => {

  let usuario = req.body;

  let update = 'UPDATE usuarios SET token = ? WHERE id = ?';
  db.query(update, ['', usuario.id], (error, rows, fields) => { });

  res.send(ok('logout'));
})

router.post('/correo/insert', async (req, res) => {

  let correo = req.body.correo;
  let correoEncrypt = encryptEmail(correo);

  let sql = 'SELECT id FROM usuarios WHERE correo = ?';
  let args = [correoEncrypt];
  let rows = await db.syncQuery(sql, args);

  if (!rows) { res.send(err('Fallo al buscar el correo en la base de datos')); return; }
  if (rows.length != 1) { res.send(err('El correo no está asociado a ningún usuario')); return; }

  let usuarioID = rows[0].id;

  sql = 'DELETE FROM correo_validacion WHERE usuario = ?';
  args = [usuarioID];
  rows = await db.syncQuery(sql, args);

  let token = randomToken(32);
  sql = 'INSERT INTO correo_validacion (usuario, token, creacion) VALUES (?, ?, now())';
  args = [usuarioID, token];
  await db.syncQuery(sql, args);

  let cuerpo = getMailBody(usuarioID, token);
  let asunto = MAIL_CONFIG.subject;

  exec(sendMailCommand(cuerpo, asunto, correo), (error, stdout, stderr) => {
    if (error || stderr) { res.send(err('Error al enviar el correo, inténtelo de nuevo')); }
    else { res.send(ok('Mensaje enviado, revise el correo')); }
  });
});

router.post('/correo/select', (req, res) => {

  let usuario = req.body.usuario;
  let token = req.body.token;

  let sql = 'SELECT u.id, u.nombre FROM correo_validacion c INNER JOIN usuarios u ON c.usuario = u.id  WHERE c.usuario = ? AND c.token = ?';
  let args = [usuario, token];
  db.query(sql, args, (error, result, fields) => {
    if (error) {
      res.send(err('Fallo al validar en la base de datos'));
    } else if (result.length != 1) {
      res.send(err('El correo no es válido'));
    } else {
      let data = {
        id: result[0].id,
        nombre: result[0].nombre
      }
      res.send(ok(data));
    }
  });
});

router.post('/password/update', async (req, res) => {

  let usuario = req.body.usuario;
  let token = req.body.token;
  let password = encryptPassword(usuario, req.body.password);

  let sql = 'SELECT u.id, u.nombre FROM correo_validacion c INNER JOIN usuarios u ON c.usuario = u.id  WHERE c.usuario = ? AND c.token = ?';
  let args = [usuario, token];
  let rows = await db.syncQuery(sql, args);

  if (rows == undefined) {
    res.send(err('Fallo al validar en la base de datos'));
  } else if (rows.length != 1) {
    res.send(err('El correo no es válido'));
  } else {

    await db.syncQuery('DELETE FROM correo_validacion WHERE usuario = ?', [usuario]);

    sql = 'UPDATE usuarios SET password = ? WHERE id = ?';
    args = [password, usuario];
    db.query(sql, args, (error, result, fields) => {
      if (error) {
        res.send(err('Error al guardar la nueva contraseña, haga una nueva solicitud'));
      } else {
        res.send(ok('Contraseña actualizada'));
      }
    });
  }
});

module.exports = router;
