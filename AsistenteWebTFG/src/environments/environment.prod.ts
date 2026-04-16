import { Usuario } from "src/models/usuario/usuario";

export const environment = {
  production: true,
  backend: 'http://corex-tfm.disca.upv.es:3000',
  session: new Usuario()
};
