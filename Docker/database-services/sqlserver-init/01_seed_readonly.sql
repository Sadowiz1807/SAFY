SET NOCOUNT ON;

IF DB_ID(N'safy_database_services') IS NULL
BEGIN
    CREATE DATABASE safy_database_services;
END
GO

ALTER DATABASE safy_database_services SET ONLINE;
GO

USE safy_database_services;
GO

IF USER_ID(N'safy_readonly') IS NOT NULL
BEGIN
    DROP USER safy_readonly;
END
GO

USE master;
GO

IF SUSER_ID(N'safy_readonly') IS NOT NULL
BEGIN
    DROP LOGIN safy_readonly;
END
GO

CREATE LOGIN safy_readonly
    WITH PASSWORD = N'safy_ro_database_services_fake_123!',
         CHECK_POLICY = OFF,
         DEFAULT_DATABASE = safy_database_services;
GO

USE safy_database_services;
GO

CREATE USER safy_readonly FOR LOGIN safy_readonly;
GO

GRANT CONNECT TO safy_readonly;
GO

ALTER ROLE db_datareader ADD MEMBER safy_readonly;
GO

IF OBJECT_ID(N'dbo.database_services_items', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.database_services_items (
        item_id INT NOT NULL CONSTRAINT PK_database_services_items PRIMARY KEY,
        name NVARCHAR(100) NOT NULL
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM dbo.database_services_items WHERE item_id = 1)
BEGIN
    INSERT INTO dbo.database_services_items (item_id, name) VALUES (1, N'demo');
END
GO

USE master;
GO
SELECT DB_ID(N'safy_database_services') AS safy_database_services_db_id;
SELECT name, default_database_name, is_disabled FROM sys.sql_logins WHERE name = N'safy_readonly';
GO

USE safy_database_services;
GO
SELECT name FROM sys.database_principals WHERE name = N'safy_readonly';
SELECT IS_ROLEMEMBER(N'db_datareader', N'safy_readonly') AS safy_readonly_is_db_datareader;
SELECT TOP 5 * FROM dbo.database_services_items ORDER BY item_id;
GO
