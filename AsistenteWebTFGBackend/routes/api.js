var express = require('express');
var router = express.Router();

var CryptoJS = require('crypto-js');

var db = require('../connection');
var fs = require('fs');
var path = require('path');

const PUBLIC = 'public';
const USER_DATA = 'user_data';
//Nuevo
const DAL = require('../DAL');

function ok(data) {
  return { ok: true, data: data, message: '' };
}

function err(message) {
  return { ok: false, data: {}, message: message }
}

function encryptEmail(email) {
  return CryptoJS.SHA3('>%+C|{JTblF(Xbn' + email, { outputLength: 256 }).toString();
}

router.post('/asignaturas', (req, res) => {

  let idUsuario = req.body.session.id;
  let cursos = [];

  let asig = false;
  let exam = false;

  function finishMerge() {
    if (asig && exam) {
      res.send(ok(cursos));
    }
  }

  function selectAsignaturas() {
    let sql = 'SELECT * FROM asignaturas WHERE usuario = ? ORDER BY curso DESC';
    db.query(sql, [idUsuario], (er, result, fields) => {
      result.forEach(asig => {
        asig.visible = asig.visible ? true : false;
        asig.disabled = false;
        cursos.find(c => c.curso == asig.curso).asignaturas.push(asig);
      });
      asig = true;
      finishMerge();
    });
  }

  function selectExamenes() {
    let sql = `SELECT a.curso, a.acronimo, a.color, e.id, e.asignatura, e.fecha, e.nombre, e.visible, e.disabled, e.isAvanzado,
      (SELECT COUNT(*) FROM calificados c WHERE c.examen = e.id) AS calificados
      FROM asignaturas a INNER JOIN examenes e ON a.id = e.asignatura
      WHERE a.usuario = ?`;
    db.query(sql, [idUsuario], (er, result, fields) => {
      result.forEach(examen => {
        examen.visible = examen.visible ? true : false;
        examen.disabled = examen.disabled ? true : false;
        cursos.find(c => c.curso == examen.curso).examenes.push(examen);
      });
      exam = true;
      finishMerge();
    });
  }

  function selectCursos() {
    let sql = 'SELECT DISTINCT(curso) FROM asignaturas WHERE usuario = ? ORDER BY curso DESC';
    db.query(sql, [idUsuario], (er, result, fields) => {
      cursos = [];
      result.forEach(curso => {
        cursos.push({
          curso: curso.curso,
          asignaturas: [],
          examenes: [],
          visible: true
        });
      });
      selectAsignaturas();
      selectExamenes();
    });
  }

  selectCursos();
});

router.post('/asignaturas/update', async (req, res) => {

  let idUsuario = req.body.session.id;
  let asignatura = req.body.data.asignatura;
  let pref = req.body.data.pref;
  let deleteAlum = req.body.data.deleteAlumnos;

  let args = [asignatura.acronimo, asignatura.color, asignatura.nombre, asignatura.id];
  let sql = 'UPDATE asignaturas SET acronimo = ?, color = ?, nombre = ? WHERE id = ?;';
  await db.syncQuery(sql, args);

  if (deleteAlum) {

    args = [pref.cabecera, pref.encode, pref.sep, idUsuario];
    sql = 'UPDATE preferencias SET cabecera = ?, encode = ?, sep = ? WHERE id = ?';
    db.query(sql, args, (er, result, fields) => { });

    args = [asignatura.id];
    sql = 'DELETE FROM alumnos WHERE asignatura = ?';
    await db.syncQuery(sql, args);
  }

  let result = await db.syncQuery('SELECT * FROM asignaturas WHERE id = ?', [asignatura.id]);
  let asig = result[0];
  asig.disabled = true;
  res.send(ok(asig));

});

router.post('/asignaturas/insert', async (req, res) => {

  let idUsuario = req.body.session.id;
  let asignatura = req.body.data.asignatura;
  let pref = req.body.data.pref;

  let args = [asignatura.acronimo, asignatura.color, asignatura.curso, asignatura.nombre, idUsuario, 1];
  let sql = 'INSERT INTO asignaturas (acronimo, color, curso, nombre, usuario, visible) VALUES (?, ?, ?, ?, ?, ?)';
  let result = await db.syncQuery(sql, args);

  let argsPref = [pref.cabecera, pref.encode, pref.sep, idUsuario];
  let sqlPref = 'UPDATE preferencias SET cabecera = ?, encode = ?, sep = ? WHERE id = ?';
  db.query(sqlPref, argsPref, (er, result, fields) => { })

  args = result.insertId;
  sql = 'SELECT * FROM asignaturas WHERE id = ?';
  result = await db.syncQuery(sql, args);

  if (result != undefined && result.length == 1) {
    let asig = result[0];
    asig.disabled = true;
    res.send(ok(asig));
  }
});

router.post('/asignaturas/select/alumnos', (req, res) => {

  let idAsignatura = req.body.data;
  let sql = 'SELECT * FROM alumnos WHERE asignatura = ?';
  db.query(sql, [idAsignatura], (er, result, fields) => {
    res.send(ok(result));
  });
});

router.post('/asignaturas/delete', (req, res) => {

  let idAsignatura = req.body.data;

  function deleteAsignatura() {
    let sql = 'DELETE FROM asignaturas WHERE id = ?';
    db.query(sql, [idAsignatura], (er, result, fields) => {
      res.send(ok(result));
    });
  }

  function deleteAlumnos() {
    let sql = 'DELETE FROM alumnos WHERE asignatura = ?';
    db.query(sql, [idAsignatura], (er, result, fields) => {
      deleteAsignatura();
    });
  }

  function canDelete() {
    let sql = 'SELECT COUNT(*) AS c FROM examenes WHERE asignatura = ?';
    db.query(sql, [idAsignatura], (er, result, fields) => {
      if (result[0].c > 0) {
        res.send(err('No se puede eliminar la asignatura si tiene exámenes relacionados'));
      } else {
        deleteAlumnos();
      }
    });
  }

  canDelete();
});

router.post('/calificado/insert', (req, res) => {

  let calificado = req.body.data;

  function selectCalificado() {

    let args = [calificado.apellidos, calificado.dni, calificado.examen, calificado.nombre];
    let sql = 'SELECT * FROM calificados WHERE apellidos = ? AND dni = ? AND examen = ? AND nombre = ?';
    db.query(sql, args, (er, result, fields) => { res.send(ok(result[0])); });
  }

  let args = [calificado.apellidos, calificado.dni, calificado.examen, calificado.fin,
  calificado.ini, calificado.nombre, calificado.nota];
  let sql = 'INSERT INTO calificados (apellidos, dni, examen, fin, ini, nombre, nota) VALUES (?, ?, ?, ?, ?, ?, ?)';

  db.query(sql, args, (er, result, fields) => { selectCalificado(); });
})

router.post('/calificado/update', (req, res) => {

  let calificado = req.body.data;

  let args = [calificado.apellidos, calificado.dni, calificado.fin,
  calificado.ini, calificado.nombre, calificado.nota, calificado.id];
  let sql = 'UPDATE calificados SET apellidos = ?, dni = ?, fin = ?, ini = ?, nombre = ?, nota = ? WHERE id = ?';

  db.query(sql, args, (er, result, fields) => { res.send(ok('debería actualizarse')) });
})

router.post('/calificado/update-automatizado', (req, res) => {
  
    let calificado = req.body.data;
  
    DAL.updateCalificadoAutomatizado(calificado).then(() => {
      res.send(ok('debería actualizarse'))
    });
  });

// 
router.post('/examen/alumnos/select', (req, res) => {

  let examen = req.body.data;

  let calificados = undefined;
  let alumnos = undefined;

  function join() {
    if (calificados != undefined && alumnos != undefined) {
      let body = { calificados: calificados, alumnos: alumnos };
      res.send(ok(body));
    }
  }

  const sql1 = `SELECT * FROM calificados WHERE examen = ?`;
  db.query(sql1, [examen.id], (er, result, fields) => {
    calificados = result;
    join();
  });

  const sql2 = `SELECT al.id, al.apellidos, al.asignatura, al.dni, al.nombre
    FROM asignaturas a INNER JOIN alumnos al ON a.id = al.asignatura 
      INNER JOIN examenes e ON a.id = e.asignatura
    WHERE al.asignatura = ? AND e.id = ? AND al.dni NOT IN (
      SELECT c.dni 
      FROM calificados c
      WHERE c.examen = e.id)
    ORDER BY al.apellidos`;
  db.query(sql2, [examen.asignatura, examen.id], (er, result, fields) => {
    result.forEach(alumno => {
      alumno.label = alumno.apellidos + ', ' + alumno.nombre + ' [' + alumno.dni + ']';
    });
    alumnos = result;
    join();
  });
});

router.post('/examen/alumnos/select-automatizado', (req, res) => {

  let examen = req.body.data;
  
  let alumnosF = undefined
  let calificadosF = undefined
  DAL.getAlumnosNoCalificados(examen.asignatura, examen.id).then(alumnos => {
    alumnosF = alumnos;
    alumnosF.forEach(alumno => {
      alumno.label = alumno.apellidos + ', ' + alumno.nombre + ' [' + alumno.dni + ']';
    });

    DAL.getCalificadosOrderByIni(examen.id).then(calificados => {
      calificadosF = calificados;
      calificadosF.forEach(calificado => {
        calificado.label = calificado.apellidos + ', ' + calificado.nombre + ' [' + calificado.dni + ']';
      });
      res.send(ok({ alumnos: alumnosF, calificados: calificadosF }));
    })
  });
}
);

router.post('/examen/select', (req, res) => {

  let idUsuario = req.body.session.id;
  let idExamen = req.body.data;

  let sql = `SELECT e.id, a.curso, a.acronimo, a.color, e.asignatura, e.fecha, e.nombre, e.visible, e.disabled, e.saltoPag, e.saltoPagActivo, e.isAvanzado, e.predicted
    FROM asignaturas a INNER JOIN examenes e ON a.id = e.asignatura 
    WHERE e.id = ? AND a.usuario = ?`;

  db.query(sql, [idExamen, idUsuario], (er, result, fields) => {

    if (er) {
      res.send(err(er));
    }
    else
      if (result.length != 1) {
        //Esto no deberia pasar nunca (?). Dios quiera que no ocurra nunca. 
        res.send(err('Resultado diferente a 1'))
      }
      else {
        let examen = result[0];
        examen['saltoPagActivo'] = examen['saltoPagActivo'] > 0 ? true : false;
        res.send(ok(result[0]));
      }
  });
});

//Nuevo examen, en la base de datos 
router.post('/examen/insert', (req, res) => {

  //console.log("Insertando examen");
  let idUsuario = req.body.session.id;
  let examen = req.body.data;

  function createDir(exam) {
    let name = idUsuario + '-' + examen.asignatura + '-' + exam.id;
    let dir = path.join(__dirname, '..', USER_DATA, name);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir);
    }
    res.send(ok(exam));
  }

  function selectExamen(id) {

    let args = [id];
    let sql = 'SELECT e.*, a.curso, a.color, a.acronimo FROM examenes e INNER JOIN asignaturas a ON e.asignatura = a.id WHERE e.id = ?';
    db.query(sql, args, (er, result, fields) => {
      if (er) { res.send(err(er)); }
      else {
        let exam = result[0];
        exam.visible = exam.visible > 0;
        exam.disabled = exam.disabled > 0;
        createDir(exam);
      }
    });
  }

  function insertExamen() {

    let args = [examen.asignatura, examen.fecha, examen.nombre, 1, 1, 0, 0, examen.isAvanzado];
    let sql = 'INSERT INTO examenes (asignatura, fecha, nombre, visible, disabled, saltoPag, saltoPagActivo, isAvanzado) VALUES (?, ?, ?, ?, ?, ?, ?, ?)';
    db.query(sql, args, (er, result, fields) => {
      if (er) { res.send(err(er)); }
      else { selectExamen(result.insertId); }
    });
  }

  insertExamen();
});

router.post('/examen/delete', (req, res) => {

  let idUsuario = req.body.session.id;
  let idExamen = req.body.data.examen;
  let idAsig = req.body.data.asignatura;

  let index = idUsuario + '-' + idAsig + '-' + idExamen;
  let privateDir = path.join(__dirname, '..', USER_DATA, index);
  let publicDir = path.join(__dirname, '..', PUBLIC, index);

  function removeCalificados() {
    let sql = 'DELETE FROM calificados WHERE examen = ?';
    db.query(sql, [idExamen], (er, result, fields) => {
      if (er) { res.send(err('Error al eliminar los calificados del examen, inténtelo de nuevo')); }
      else { removeExamen(); }
    });
  }

  function removeExamen() {
    let sql = 'DELETE FROM examenes WHERE id = ?';
    db.query(sql, [idExamen], (er, result, fields) => {
      if (er) { res.send(err('Error al eliminar el examen, inténtelo de nuevo')); }
      else { res.send(ok('Se debería haber borrado')); }
    });
  }

  function removePublicDir() {
    if (fs.existsSync(publicDir)) {
      fs.rmdir(publicDir, { recursive: true }, (er) => {
        if (er) { res.send(err('No se pudo eliminar el directorio, inténtelo de nuevo')); }
        else { removeCalificados(); }
      });
    } else {
      removeCalificados();
    }
  }

  function removePrivateDir() {
    if (fs.existsSync(privateDir)) {
      fs.rmdir(privateDir, { recursive: true }, (er) => {
        if (er) { res.send(err('No se pudo eliminar el directorio, inténtelo de nuevo')); }
        else { removePublicDir(); }
      });
    } else {
      removePublicDir();
    }
  }

  removePrivateDir();
});

router.post('/examen/zip', (req, res) => {

  let idUsuario = req.body.session.id;
  let filename = req.body.data;


  fs.readFile(path.join(__dirname, '..', filename.replace(' ', '_')), (er, data) => {
    if (er) {
      res.send(err(er))
    } else {
      res.send(ok(data.toString()))
    }
  });
});

router.post('/examen/update/saltoPag', (req, res) => {

  let idUsuario = req.body.session.id;
  let idExamen = req.body.data.examen;
  let saltoPag = req.body.data.saltoPag;
  let saltoPagActivo = req.body.data.saltoPagActivo;

  let args = [saltoPag, saltoPagActivo, idExamen];
  let sql = 'UPDATE examenes SET saltoPag = ?, saltoPagActivo = ? WHERE id = ?';
  db.query(sql, args, (er, result, fields) => { });
  res.send(ok(''));
});

router.post('/usuario/update/correo', async (req, res) => {

  let idUsuario = req.body.session.id;
  let correo = req.body.data;

  let encryptCorreo = encryptEmail(correo);

  let args = [encryptCorreo];
  let sql = 'SELECT id FROM usuarios WHERE correo = ?';
  let rows = await db.syncQuery(sql, args);

  if (!rows) { res.send(err('Fallo al buscar el correo en la base de datos')); return; }
  if (rows.length > 0) { res.send(err('El correo ya está en uso')); return; }

  //console.log(encryptCorreo);

  args = [encryptCorreo, idUsuario];
  sql = 'UPDATE usuarios SET correo = ? WHERE id = ?';
  db.query(sql, args, (er, result, fields) => {
    if (er) { res.send(err('Error al guardar el nuevo correo')); }
    else { res.send(ok('Correo actualizado')); }
  });
});

router.post('/preferencias/select', (req, res) => {

  let idUsuario = req.body.session.id;

  let args = [idUsuario];
  let sql = 'SELECT encode, sep, cabecera FROM preferencias WHERE id = ?';
  db.query(sql, args, (er, result, fields) => {
    if (er || result.length != 1) {
      let pref = { encode: 'utf8', sep: ';', cabecera: false }
      res.send(ok(pref));
    } else {
      result[0].cabecera = result[0].cabecera == 1;
      res.send(ok(result[0]));
    }
  });

});

router.post('/prediction/statistics', async (req, res) => {

  let asignatura = req.body.data;
  let intersecciones = []
  let diferencias = []
  let errores = []

  DAL.getCalificadosOrderByIni(asignatura).then(calificados => {

    for (let i = 0; i < calificados.length; ++i) {
      //Comprobamos predicciones imposibles o incompletas
      if (calificados[i].dni.startsWith("Err"))
        errores.push(calificados[i]);
      //Salvo que sea el último
      if(i!=calificados.length-1){
        //Comprobamos que no se intersecten
        if (calificados[i].fin >= calificados[i + 1].ini)
          intersecciones.push(calificados[i]);
        //Comprobamos que no haya diferencias
        if (calificados[i + 1].ini - calificados[i].fin > 1)
          diferencias.push(calificados[i]);
      }
    }

    let stats = {
      intersecciones: intersecciones,
      diferencias: diferencias,
      errores: errores
    }
    res.send(ok(stats));


  });

});

module.exports = router;
