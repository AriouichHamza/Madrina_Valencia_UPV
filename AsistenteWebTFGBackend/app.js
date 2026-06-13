var createError = require('http-errors');
var express = require('express');
var fs = require('fs');
var path = require('path');
var cookieParser = require('cookie-parser');
var logger = require('morgan');
var cors = require('cors');

var db = require('./connection');

var interceptorRouter = require('./routes/interceptor');
var apiRouter = require('./routes/api');
var loginRouter = require('./routes/login');

var app = express();

// Ensure the runtime directories exist before any request is served.
if (!fs.existsSync(path.join(__dirname, 'public'))) {
  fs.mkdirSync( path.join(__dirname, 'public') );
}

if (!fs.existsSync(path.join(__dirname, 'user_data'))) {
  fs.mkdirSync( path.join(__dirname, 'user_data') );
}

// Abort early if the database is unreachable — the app cannot function without it.
db.isConnected((connected, err) => {
  if (!connected) {
    const host = process.env.DB_HOST || '127.0.0.1';
    const port = process.env.DB_PORT || '3306';
    const database = process.env.DB_NAME || 'MargotDB';
    const code = err && (err.code || err.errno || err.message);
    console.error(
      `Could not connect to MySQL at ${host}:${port}/${database}` +
      (code ? ` (${code})` : '')
    );
    process.exit(1);
  }
});

// View engine setup — Pug templates are used only for error pages.
app.set('views', path.join(__dirname, 'views'));
app.set('view engine', 'pug');

app.use(logger('dev'));
app.use(express.json());
app.use(express.urlencoded({ extended: false }));
app.use(cookieParser());
app.use('/info', express.static(path.join(__dirname, 'info')));
app.use('/public', express.static(path.join(__dirname, 'public')));
// CORS is open to all origins — restrict to the frontend domain before going public.
app.use(cors({ origin: '*' }));

// The interceptor checks the session token before every /api request.
app.use('/api', interceptorRouter);
app.use('/api', apiRouter);
app.use('/login', loginRouter);

// catch 404 and forward to error handler
app.use(function(req, res, next) {
  next(createError(404));
});

// error handler
app.use(function(err, req, res, next) {
  // set locals, only providing error in development
  res.locals.message = err.message;
  res.locals.error = req.app.get('env') === 'development' ? err : {};

  // render the error page
  res.status(err.status || 500);
  res.render('error');
});

module.exports = app;
