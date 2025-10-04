-- Script inicial para provisionar usuário e database dedicados no Cloud SQL (Postgres)
-- Execute conectado como usuário postgres administrador.

-- 1. Criar database (ajuste collation/ctype se necessário para pt_BR):
CREATE DATABASE pandora_app ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0;

-- 2. Criar usuário dedicado com senha forte (substitua SENHA_FORTE):
CREATE USER pandora_user WITH PASSWORD 'SENHA_FORTE';

-- 3. Transferir ownership e permissões:
GRANT ALL PRIVILEGES ON DATABASE pandora_app TO pandora_user;
ALTER DATABASE pandora_app OWNER TO pandora_user;

-- 4. (Opcional) Extensões necessárias no futuro:
-- \c pandora_app
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- CREATE EXTENSION IF NOT EXISTS uuid-ossp;

-- 5. Revogar permissões amplas de public se desejar hardening adicional (avaliar impacto):
-- REVOKE CREATE ON SCHEMA public FROM PUBLIC;
-- GRANT USAGE ON SCHEMA public TO pandora_user;
-- GRANT CREATE ON SCHEMA public TO pandora_user;

-- 6. Checklist pós-execução:
-- - Atualize env.yaml com a senha (URL-encoded se contiver caracteres especiais)
-- - Faça deploy novamente: gcloud app deploy app.yaml --quiet
-- - Verifique logs de migração (Cloud Logging) para confirmar sucesso
