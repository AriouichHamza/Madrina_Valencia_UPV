
const db = require('../connection');
const archiver = require('archiver');
const fs = require('fs');
const path = require('path');
const pdfPageCounter = require('pdf-page-counter');
var PDFMerger = require('pdf-merger-js');

const DAL = require('../DAL');

const { exec, execSync, spawn } = require("child_process");

const PUBLIC = 'public';
const USER_DATA = 'user_data';
const os = require("os");

async function pdftoppm(read, write, pages, socket, idExam) {

  return new Promise((resolve, reject) => {

    let done = true;
    let ini = 1, fin = 0, cont = 1;
    let contExec = 0, cantExec = 0;
    while (ini <= pages) {

      fin = ((ini + 49) <= pages) ? (ini + 49) : pages;

      let command = pdftoppmCommand(read, ini, fin, write);
      contExec++;
      cantExec++;
      socket.emit('insert-examen-preparar', { idExam: idExam, cont: contExec, total: cantExec * 2 });
      exec(command, (error, stdout, stderr) => {
        if (error) { console.error(error); done = false; }
        contExec++;
        socket.emit('insert-examen-preparar', { idExam: idExam, cont: contExec, total: cantExec * 2 });
        if (contExec == (cantExec * 2)) resolve(done);
      });
      ini = fin + 1;
    }
  });
}

async function pdfunite(readdir, writefile) {

  return new Promise((resolve, reject) => {

    let done = true;
    let listFiles = '';
    let files = fs.readdirSync(readdir);
    files.forEach(file => {
      listFiles += `"${path.join(readdir, file)}" `;
    });
    let command = `pdfunite ${listFiles} "${writefile}"`;
    console.log(command);
    exec(command, (error, stdout, stderr) => {
      if (error) { console.error(error); done = false; }
      resolve(done);
    });
  });

}

async function ps2pdf(readdir, socket, idExam) {

  return new Promise((resolve, reject) => {

    let done = true;
    let contExec = 0, cantExec = 0;
    let files = fs.readdirSync(readdir);
    for (let i = 0; i < files.length; i++) {
      let absolute = path.join(readdir, files[i]);
      let newAbsolute = path.join(readdir, 'ps2pdf-' + files[i]);
      let command = `ps2pdf "${absolute}" "${newAbsolute}"`;
      cantExec++;
      exec(command, (error, stdout, stderr) => {
        if (error) { console.error(error); done = false; }
        contExec++
        socket.emit('insert-examen-generar', { idExam: idExam, cont: contExec, total: cantExec });
        if (contExec == cantExec) resolve(done);
      });

    }
  });
}

async function ps2pdfRemoveFiles(startsWith, readdir) {

  return new Promise((resolve, reject) => {

    let done = true;
    let contExec = 0, cantExec = 0;

    fs.readdir(readdir, (err, files) => {
      if (err) { console.error(err); resolve(false); }

      cantExec = files.length;
      files.forEach(file => {
        contExec++;
        if ((startsWith && file.startsWith('ps2pdf-')) || (!startsWith && !file.startsWith('ps2pdf-'))) {
          let dirfile = path.join(readdir, file);
          fs.unlink(dirfile, (err) => {
            if (err) { console.error(err); done = false; }
            if (contExec == cantExec) resolve(done);
          });
        }
      });
    });
  });

}

function pdftoppmCommand(read, s, f, write) {
  let x = 1240;
  let y = 1750;
  let dpi = 150

  return `pdftoppm -jpeg -f ${s} -l ${f} -r ${dpi} -scale-to-x ${x} -scale-to-y ${y} "${read}" "${write}"`;
}

//Windows & MacOs
//var pdfPoppler = require('pdf-poppler');

const connection = async (socket) => {

  console.log('\x1b[32mclient', socket.id, '\x1b[0m');

  let fileBuffer = [];

  socket.on('insert-alumno', (data) => {
    let args = [data.apellidos.trim(), data.asignatura, data.dni.trim(), data.nombre.trim()];
    let sql = 'INSERT INTO alumnos (apellidos, asignatura, dni, nombre) VALUES (?, ?, ?, ?)';
    db.query(sql, args, (er, result, fields) => {
      data = {
        asignatura: data.asignatura,
        i: data.i
      }
      socket.emit('insert-alumno', data);
    });
  });

  socket.on('insert-examen', (data) => {

    let idUsuario = data.usuario;
    let idAsig = data.asignatura;
    let idExam = data.examen;
    let idPaquete = data.paquete.id
    let op = data.paquete.op;
    let payload = data.paquete.payload;

    let index = idUsuario + '-' + idAsig + '-' + idExam;


    function createImgsWin(dir, fileName) {

      const convertImgSync = async (dir, fileName) => {

        let opts = {
          format: 'jpg',
          out_dir: dir,
          out_prefix: fileName.substring(0, fileName.length - 4),
          page: null
        }

        let readFile = path.join(dir, fileName);
        let pages = await pdfPageCounter(fs.readFileSync(readFile));

        let interval = setInterval(() => {
          let files = fs.readdirSync(dir);
          socket.emit('insert-examen-preparar', { idExam: idExam, cont: files.length, pages: pages.numpages });
        }, 1000);

        await pdfPoppler.convert(readFile, opts);

        clearInterval(interval);
      }

      convertImgSync(dir, fileName).then(() => {
        let sql = 'UPDATE examenes SET disabled = ? WHERE id = ?';
        db.query(sql, [0, idExam], (er, result, fields) => {
          socket.emit('insert-examen-listo', idExam);
        });
      });

    }

    async function insertExamenError(message) {
      console.error(message);

      let dir = path.join(__dirname, '..', USER_DATA, index);
      fs.rm(dir, { recursive: true }, (err) => {
        if (err) { console.error('No se ha podido borrar la carpeta ' + index); }
      });

      db.query('DELETE FROM examenes WHERE id = ?', [idExam], (er, result, fields) => {
        if (er) { console.error('No se ha podido borrar de la base de datos el examen ' + index); }
        socket.emit('insert-examen-error', { idExam: idExam, message: 'Error al procesar el examen' });
      });
    }

    async function mergeFiles(baseName, baseIndex, cant) {

      for (let i = 0; i < cant; i++) {
        if (fileBuffer[baseIndex + i] == undefined || !fileBuffer[baseIndex + i].ready) return;
      }

      for (let i = 0; i < cant; i++) { delete fileBuffer[baseIndex + i]; }

      let readdir = path.join(__dirname, '..', USER_DATA, index);
      let writefile = path.join(readdir, baseName);

      //esto puede que se pueda eliminar
      let done = await ps2pdf(readdir, socket, idExam);
      if (!done) { insertExamenError('ps2pdf'); return; }

      done = await ps2pdfRemoveFiles(false, readdir);
      if (!done) { insertExamenError('false ps2pdfRemoveFiles'); return; }

      done = await pdfunite(readdir, writefile);
      if (!done) { insertExamenError('pdfunite'); return; }

      socket.emit('insert-examen-generar', { idExam: idExam, cont: 1, total: 1 });

      done = await ps2pdfRemoveFiles(true, readdir);
      if (!done) { insertExamenError('true ps2pdfRemoveFiles'); return; }

      if (process.platform == 'linux') {

        let readFile = path.join(readdir, baseName);
        let writeFile = path.join(readdir, path.parse(readFile).name);

        let pages = null;
        try {
          pages = (await pdfPageCounter(fs.readFileSync(readFile))).numpages;
        } catch (e) {
          insertExamenError('pdfPageCounter'); return;
        }
        if (pages == 0) { insertExamenError('pdfPageCounter'); return; }

        socket.emit('insert-examen-preparar', { idExam: idExam, cont: 0, total: 1 });

        done = await pdftoppm(readFile, writeFile, pages, socket, idExam);
        if (!done) { insertExamenError('pdftoppm'); return; }

        let sql = 'UPDATE examenes SET disabled = ? WHERE id = ?';
        let args = [0, idExam];
        db.query(sql, args, (er, result, fields) => {
          if (er) {
            console.error('Error al actualizar el examen ' + index);
            socket.emit('insert-examen-error', { idExam: idExam, message: 'Error al procesar el examen' });
          } else {
            socket.emit('insert-examen-listo', { idExam: idExam });
          }
        });

      } else {
        createImgsWin(readdir, baseName);
      }
    }

    switch (op) {
      case 'new-file':
        fileBuffer[idPaquete] = { nombre: payload, data: '', ready: false };
        socket.emit('insert-examen-procesar', idExam);
        break;
      case 'fin-file':

        let baseName = payload.split(':')[0];
        let baseIndex = payload.split(':')[1];
        let cant = parseInt(payload.split(':')[2]);

        socket.emit('insert-examen-procesar', idExam);

        let fileName = fileBuffer[idPaquete].nombre;
        let data = fileBuffer[idPaquete].data;
        data = data.split(';base64,').pop();

        let dir = path.join(__dirname, '..', USER_DATA, index, fileName.replace(' ', '_'));
        let done = true;
        fs.writeFileSync(dir, data, 'base64', (error) => {
          if (error) {
            console.error(error);
            done = false;
          }
        });

        if (!done) { insertExamenError('writeFileSync base64'); return; }

        socket.emit('insert-examen-crear', idExam);
        fileBuffer[idPaquete].ready = true;

        mergeFiles(baseName.replace(' ', '_'), baseIndex, cant);

        break;
      default:
        fileBuffer[idPaquete].data += payload;
        socket.emit('insert-examen-procesar', idExam);
        break;
    }
  });
  //Devuelve las imagenes de un examen dados los id de usuario, asignatura y examen 
  socket.on('select-examen-imgs', (data) => {

    let idUsuario = data.usuario;
    let idAsig = data.asignatura;
    let idExam = data.examen;
    let index = idUsuario + '-' + idAsig + '-' + idExam;

    function splitString(base64) {

      const length = 1024 * 256;
      let split = [];

      while (base64.length > length) {
        let o = base64.substring(0, length);
        let f = base64.substring(length, base64.length);
        split.push(o);
        base64 = f;
      }
      split.push(base64.substring(0, base64.length));

      return split;
    }

    let readdir = path.join(__dirname, '..', USER_DATA, index);
    let files = [];
    if (fs.existsSync(readdir)) {
      files = fs.readdirSync(readdir);
    }

    files.forEach(file => {

      if (path.extname(file).toLowerCase() == '.jpg') {
        let data = fs.readFileSync(path.join(readdir, file), { encoding: 'base64' });
        let split = splitString(data);
        socket.emit('select-examen-imgs', 'new-img');
        socket.emit('select-examen-imgs', 'data:image/jpg;base64,');
        split.forEach(paquete => {
          socket.emit('select-examen-imgs', paquete);
        });
        socket.emit('select-examen-imgs', 'fin-imgs');
      };
    });
    //Evento que indica que se han enviado todas las imagenes
    socket.emit('select-examen-imgs', 'fin-all');

  });

  socket.on('select-examen-zip', async (data) => {

    let examen = { nombre: '', fecha: 0 };

    let idUsuario = data.usuario;
    let idAsig = data.asignatura;
    let idExam = data.examen;
    let index = idUsuario + '-' + idAsig + '-' + idExam;

    examen = (await db.syncQuery('SELECT * FROM examenes WHERE id = ?', [idExam]))[0];

    let dirPrivate = path.join(__dirname, '..', USER_DATA, index);
    let dirPublic = path.join(__dirname, '..', PUBLIC, index);

    let dirExamen = path.join(dirPublic, examen.nombre)
    let dirCSV = path.join(dirExamen, 'csv');
    let dirExamenes = path.join(dirExamen, 'examenes');

    if (fs.existsSync(dirPublic)) { fs.rmSync(dirPublic, { recursive: true }); }
    fs.mkdirSync(dirPublic);
    fs.mkdirSync(dirExamen);
    fs.mkdirSync(dirCSV);
    fs.mkdirSync(dirExamenes);

    let progressTotal = 0;
    let progress = 0;

    function dniWithoutCheckLetter(value) {
      const dni = String(value || '').trim().toUpperCase();

      if (/^\d+[A-Z]$/.test(dni) || /^[XYZNP]\d+[A-Z]$/.test(dni)) {
        return dni.slice(0, -1);
      }

      return dni;
    }

    function writeZIP() {

      if (progress < progressTotal) {
        let paquete = {
          done: false,
          progress: progress,
          total: progressTotal,
          perc: Math.round(progress / progressTotal)
        }
        console.log('progress: %d progressTotal', progress, progressTotal);
        socket.emit('select-examen-zip', paquete);
        return;
      }

      let date = new Date(examen.fecha);
      let year = date.getFullYear();
      let month = ((date.getMonth() + 1) < 9) ? '0' + date.getMonth() + 1 : date.getMonth() + 1;
      let day = (date.getDate() < 9) ? '0' + date.getDate() : date.getDate();
      let filename = `${year}${month}${day}-${examen.nombre.replace(' ', '_')}.zip`;
      let filePath = path.join(dirPublic, filename);

      const output = fs.createWriteStream(filePath);
      const archive = archiver('zip', { zlib: { level: 9 } });

      output.on('close', function () {
        fs.rmSync(dirCSV, { recursive: true });
        fs.rmSync(dirExamenes, { recursive: true });

        let paquete = {
          done: true,
          progress: progressTotal,
          total: progressTotal,
          filename: filename,
          url: PUBLIC + '/' + index + '/' + filename
        }
        console.log('emit on close');
        socket.emit('select-examen-zip', paquete);
      });
      console.log('archive');
      archive.pipe(output);
      archive.directory(dirExamen, examen.nombre);
      archive.finalize();
    }

    function writeCSV(calificados) {

      let csvInfo = 'ID estudiante;Apellidos;Nombre;Nota;Inicio;Fin\n';
      let csvPadrino = 'ID estudiente;Nota\n';

      calificados.forEach(c => {
        const exportedDni = dniWithoutCheckLetter(c.dni);
        csvInfo += `${exportedDni};${c.apellidos};${c.nombre};${c.nota};${c.ini};${c.fin}\n`;
        if (exportedDni.length > 0) { csvPadrino += `${exportedDni};${c.nota}\n`; }
      });
      csvInfo = csvInfo.trim();
      csvPadrino = csvPadrino.trim();

      let filenameInfo = 'detalles.csv';
      let filenameExamenes = examen.nombre.replace(' ', '_') + '_notas_padrino.csv';

      fs.writeFileSync(path.join(dirCSV, filenameInfo), csvInfo);
      fs.writeFileSync(path.join(dirCSV, filenameExamenes), csvPadrino);

      progress++;
      writeZIP();
    }
    function writePDFLinux(calificados) {

    }

    /*function writePDF(calificados) {

      let sinNombre = 0;

      const userHomeDir = os.homedir();
      let readdir = path.join(userHomeDir, 'exam_scan/sube.bat');
      let writedir = path.join(dirExamenes, 'sube.bat');
      console.log('readdir: %s writedir %s', readdir, writedir);
      fs.copyFileSync(readdir, writedir);
      calificados.forEach(c => {

        let filename = '';

        if (c.dni.length > 0) {

          let alumnoDNI = c.dni.toUpperCase();
          let examenNombre = examen.nombre.replace(' ', '_');
          let alumnoNombre = (
            c.nombre.replace(' ', '_') +
            '_' +
            c.apellidos.replace(' ', '_')
          ).toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "");

          filename = `${alumnoDNI}_${examenNombre}_${alumnoNombre}.pdf`;
        } else {
          filename = 'XXXXXXXXX_Sin_nombre_' + (++sinNombre) + '.pdf';
        }

        let writedir = path.join(dirExamenes, filename);
        let readdir = path.join(dirPrivate, (examen.nombre.replace(' ', '_') + '.pdf'))
        let pages = (c.ini == c.fin) ? ([c.ini]) : (c.ini + '-' + c.fin);


        let command = `cpdf ${readdir}  ${pages} -o "${writedir}" > /dev/null`;
        //console.log ('comnad: %s', command);
        execSync(command);

        progress++;
        writeZIP();
        /*
        let merger = new PDFMerger();
        
        merger.add(readdir, pages);
        console.log ('readdir %s writedir %s pages %s progress %d', readdir, writedir, pages, progress);
        merger.save(writedir).then(response => {
          progress++;
          writeZIP();
        }).catch(err => { console.error(err); });
        *-/
      });
    } */
  function writePDF(calificados) {
    let sinNombre = 0;

    const userHomeDir = os.homedir();
    const scanBat = path.join(userHomeDir, 'exam_scan', 'sube.bat');
    const destBat = path.join(dirExamenes, 'sube.bat');

    console.log('scanBat: %s destBat: %s', scanBat, destBat);

    // Copier sube.bat seulement s'il existe
    if (fs.existsSync(scanBat)) {
      fs.copyFileSync(scanBat, destBat);
    } else {
      console.log('sube.bat absent, copie ignorée');
    }

    calificados.forEach(c => {
      let filename = '';
      const exportedDni = dniWithoutCheckLetter(c.dni);

      if (exportedDni.length > 0) {
        let alumnoDNI = exportedDni;
        let examenNombre = examen.nombre.replace(/ /g, '_');
        let alumnoNombre = (
          c.nombre.replace(/ /g, '_') +
          '_' +
          c.apellidos.replace(/ /g, '_')
        )
          .toLowerCase()
          .normalize("NFD")
          .replace(/\p{Diacritic}/gu, "");

        filename = `${alumnoDNI}_${examenNombre}_${alumnoNombre}.pdf`;
      } else {
        filename = 'XXXXXXXXX_Sin_nombre_' + (++sinNombre) + '.pdf';
      }

      const writePath = path.join(dirExamenes, filename);
      const readPath = path.join(dirPrivate, examen.nombre.replace(/ /g, '_') + '.pdf');
      const pages = (c.ini == c.fin) ? `${c.ini}` : `${c.ini}-${c.fin}`;

      try {
        let command = `cpdf "${readPath}" ${pages} -o "${writePath}" > /dev/null`;
        execSync(command);
        progress++;
        writeZIP();
      } catch (err) {
        console.error('Erreur writePDF/cpdf:', err.message);
      }
    });
  }

      let sql = 'SELECT * FROM calificados WHERE examen = ?';
      db.query(sql, [idExam], (er, result, fields) => {
        progressTotal = result.length + 1;
        writeCSV(result);
        writePDF(result);
      });
    });

  //const command = "python3"
  const command = "../.venv/bin/python";
  const pathToScript = path.join(__dirname, '..', '..', 'AsistenteWebTFGBackendAIModule', 'main.py');
  const aiModuleUserDataRoot = path.join(__dirname, '..', USER_DATA);
  let childProcesses = {};

  socket.on('examen-predict', async (data) => {

    //Datos para localizar el examen
    let usuario = data.usuario;
    let asignatura = data.asignatura;
    let examen = data.examen;

    let asignaturaNom = data.asignaturaNom;
    let index = usuario + '-' + asignatura + '-' + examen;
    //Ya hay un proceso en marcha
    if (childProcesses[index]) { //Si ya está en marcha nos enganchamos al proceso
      
      //TO-DO
      //Emitir señal de que ya se está procesando
      return;
    }
    //Obtener todos los alumnos de ese examen

    let progressconversion = 0;
    let progressFindStructure = 0;
    DAL.getAlumnosFromAsignatura(asignatura).then((result) => {
      let alumnosJson = JSON.stringify(result);
      let args = [pathToScript, index, asignaturaNom, alumnosJson]
      const child = spawn(command, args, {
        cwd: path.dirname(pathToScript),
        env: {
          ...process.env,
          AI_MODULE_USER_DATA_ROOT: aiModuleUserDataRoot,
        },
      })
      //guardamos el proceso hijo
      childProcesses[index] = child;

      let prediccionesAlumnos = [];
      child.stdout.on('data', (data) => {

        let output = data.toString('utf-8').trim();
        //Split en caso de que lleguen varias lineas en un solo mensaje
        //Cada linea será una unidad independiente de informacion
        output.split('\n').forEach(element => {
          let splitted = element.split(' ')
          let preamble = splitted[0]
          let data = splitted.slice(1, splitted.length).join(' ').trim()

          switch (preamble) {
            case "progress":
              let state = splitted.slice(2, splitted.length).join(' ').trim()
              
              switch (state) {
                case "Buscando DNIs en páginas":
                  if (Number(splitted[1]) > progressFindStructure) {
                    progressFindStructure = splitted[1]
                    socket.emit('examen-predict-response', element)
                  }
                  break;
                case "Convirtiendo PDF a imagenes":
                  if (splitted[1] > progressconversion) {
                    progressconversion = splitted[1]
                    socket.emit('examen-predict-response', element)
                  }
                  break;
              }
              break;
            case "new-calificado":
              let dataJson = JSON.parse(data)
              prediccionesAlumnos.push(dataJson);
              break;
            case "done":
              //Añadimos las predicciones en la base de datos
              prediccionesAlumnos.forEach(alumno => {
                DAL.insertAlumnoCalificado(alumno, false)
              });
              //Marcamos el examen como predicho
              DAL.setExamenIsPredicted(examen, true);
              socket.emit('examen-predict-response', element);
              break;
          }



        });
      });

      child.stderr.on('data', (data) => {
        console.error(data.toString('utf-8'));
      });
      child.on('exit', (code) => {
        delete childProcesses[index];
        //console.log(`Child exited with code ${code}`);
      });

    });






  });


}


const use = (server) => {

  let pingTimeout = 5 * 60 * 1000;

  console.log('socket - pingTimeout:', pingTimeout);

  var io = require('socket.io')(server, { pingTimeout: pingTimeout });

  io.on('connection', connection);
}

module.exports = use;
