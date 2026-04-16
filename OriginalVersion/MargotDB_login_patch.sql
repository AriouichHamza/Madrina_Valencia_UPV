USE MargotDB;

-- Normalize already-inserted rows
UPDATE usuarios
SET
  nombre = COALESCE(NULLIF(nombre, ''), nom),
  nom = COALESCE(NULLIF(nom, ''), nombre),
  email = COALESCE(NULLIF(email, ''), correo),
  correo = COALESCE(NULLIF(correo, ''), email),
  mot_de_passe = COALESCE(NULLIF(mot_de_passe, ''), password),
  password = COALESCE(NULLIF(password, ''), mot_de_passe);

UPDATE correo_validacion
SET
  usuario_id = COALESCE(usuario_id, usuario),
  usuario = COALESCE(usuario, usuario_id),
  code_validation = COALESCE(NULLIF(code_validation, ''), codigo),
  codigo = COALESCE(NULLIF(codigo, ''), code_validation),
  valide = COALESCE(valide, validado),
  validado = COALESCE(validado, valide, 1);

UPDATE preferencias
SET usuario_id = COALESCE(usuario_id, id);

DROP TRIGGER IF EXISTS bi_usuarios_sync;
DROP TRIGGER IF EXISTS bu_usuarios_sync;
DROP TRIGGER IF EXISTS ai_usuarios_defaults;
DROP TRIGGER IF EXISTS bi_correo_validacion_sync;
DROP TRIGGER IF EXISTS bu_correo_validacion_sync;
DROP TRIGGER IF EXISTS bi_preferencias_sync;
DROP TRIGGER IF EXISTS bu_preferencias_sync;

DELIMITER $$

CREATE TRIGGER bi_usuarios_sync
BEFORE INSERT ON usuarios
FOR EACH ROW
BEGIN
    IF NEW.nombre IS NULL OR NEW.nombre = '' THEN SET NEW.nombre = NEW.nom; END IF;
    IF NEW.nom IS NULL OR NEW.nom = '' THEN SET NEW.nom = NEW.nombre; END IF;
    IF NEW.email IS NULL OR NEW.email = '' THEN SET NEW.email = NEW.correo; END IF;
    IF NEW.correo IS NULL OR NEW.correo = '' THEN SET NEW.correo = NEW.email; END IF;
    IF NEW.mot_de_passe IS NULL OR NEW.mot_de_passe = '' THEN SET NEW.mot_de_passe = NEW.password; END IF;
    IF NEW.password IS NULL OR NEW.password = '' THEN SET NEW.password = NEW.mot_de_passe; END IF;
END$$

CREATE TRIGGER bu_usuarios_sync
BEFORE UPDATE ON usuarios
FOR EACH ROW
BEGIN
    IF NEW.nombre IS NULL OR NEW.nombre = '' THEN SET NEW.nombre = NEW.nom; END IF;
    IF NEW.nom IS NULL OR NEW.nom = '' THEN SET NEW.nom = NEW.nombre; END IF;
    IF NEW.email IS NULL OR NEW.email = '' THEN SET NEW.email = NEW.correo; END IF;
    IF NEW.correo IS NULL OR NEW.correo = '' THEN SET NEW.correo = NEW.email; END IF;
    IF NEW.mot_de_passe IS NULL OR NEW.mot_de_passe = '' THEN SET NEW.mot_de_passe = NEW.password; END IF;
    IF NEW.password IS NULL OR NEW.password = '' THEN SET NEW.password = NEW.mot_de_passe; END IF;
END$$

CREATE TRIGGER ai_usuarios_defaults
AFTER INSERT ON usuarios
FOR EACH ROW
BEGIN
    INSERT INTO preferencias (id, usuario_id, encode, sep, cabecera)
    SELECT NEW.id, NEW.id, 'utf8', ';', 0
    FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM preferencias p WHERE p.id = NEW.id);

    INSERT INTO correo_validacion (usuario, usuario_id, codigo, code_validation, validado, valide)
    SELECT NEW.id, NEW.id, CONCAT('auto-', NEW.id), CONCAT('auto-', NEW.id), 1, 1
    FROM DUAL
    WHERE NOT EXISTS (SELECT 1 FROM correo_validacion c WHERE c.usuario = NEW.id OR c.usuario_id = NEW.id);
END$$

CREATE TRIGGER bi_correo_validacion_sync
BEFORE INSERT ON correo_validacion
FOR EACH ROW
BEGIN
    IF NEW.usuario_id IS NULL THEN SET NEW.usuario_id = NEW.usuario; END IF;
    IF NEW.usuario IS NULL THEN SET NEW.usuario = NEW.usuario_id; END IF;
    IF NEW.code_validation IS NULL OR NEW.code_validation = '' THEN SET NEW.code_validation = NEW.codigo; END IF;
    IF NEW.codigo IS NULL OR NEW.codigo = '' THEN SET NEW.codigo = NEW.code_validation; END IF;
    IF NEW.valide IS NULL THEN SET NEW.valide = COALESCE(NEW.validado, 1); END IF;
    IF NEW.validado IS NULL THEN SET NEW.validado = COALESCE(NEW.valide, 1); END IF;
END$$

CREATE TRIGGER bu_correo_validacion_sync
BEFORE UPDATE ON correo_validacion
FOR EACH ROW
BEGIN
    IF NEW.usuario_id IS NULL THEN SET NEW.usuario_id = NEW.usuario; END IF;
    IF NEW.usuario IS NULL THEN SET NEW.usuario = NEW.usuario_id; END IF;
    IF NEW.code_validation IS NULL OR NEW.code_validation = '' THEN SET NEW.code_validation = NEW.codigo; END IF;
    IF NEW.codigo IS NULL OR NEW.codigo = '' THEN SET NEW.codigo = NEW.code_validation; END IF;
    IF NEW.valide IS NULL THEN SET NEW.valide = COALESCE(NEW.validado, 1); END IF;
    IF NEW.validado IS NULL THEN SET NEW.validado = COALESCE(NEW.valide, 1); END IF;
END$$

CREATE TRIGGER bi_preferencias_sync
BEFORE INSERT ON preferencias
FOR EACH ROW
BEGIN
    IF NEW.usuario_id IS NULL THEN SET NEW.usuario_id = NEW.id; END IF;
END$$

CREATE TRIGGER bu_preferencias_sync
BEFORE UPDATE ON preferencias
FOR EACH ROW
BEGIN
    IF NEW.usuario_id IS NULL THEN SET NEW.usuario_id = NEW.id; END IF;
END$$

DELIMITER ;
