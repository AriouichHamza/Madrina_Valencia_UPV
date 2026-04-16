USE MargotDB;

-- Synchronize legacy/new column names for all existing users
UPDATE usuarios
SET
  nombre = COALESCE(NULLIF(nombre, ''), nom),
  nom = COALESCE(NULLIF(nom, ''), nombre),
  correo = COALESCE(NULLIF(correo, ''), email),
  email = COALESCE(NULLIF(email, ''), correo),
  password = COALESCE(NULLIF(password, ''), mot_de_passe),
  mot_de_passe = COALESCE(NULLIF(mot_de_passe, ''), password);

-- Ensure validation rows exist for every user
INSERT INTO correo_validacion (usuario, usuario_id, codigo, code_validation, validado, valide)
SELECT u.id, u.id, CONCAT('auto-', u.id), CONCAT('auto-', u.id), 1, 1
FROM usuarios u
LEFT JOIN correo_validacion cv ON cv.usuario = u.id OR cv.usuario_id = u.id
WHERE cv.id IS NULL;

-- Auto-validate all existing validation rows
UPDATE correo_validacion
SET validado = 1,
    valide = 1,
    codigo = COALESCE(NULLIF(codigo, ''), code_validation, CONCAT('auto-', usuario)),
    code_validation = COALESCE(NULLIF(code_validation, ''), codigo, CONCAT('auto-', usuario));

-- Optional consistency report
SELECT u.id, u.nom, u.nombre, u.email, u.correo, u.password, u.mot_de_passe,
       cv.validado, cv.valide
FROM usuarios u
LEFT JOIN correo_validacion cv ON cv.usuario = u.id OR cv.usuario_id = u.id
ORDER BY u.id DESC;
