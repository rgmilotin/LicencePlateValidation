#include "parkingdb.hpp"
#include <iostream>

ParkingDB::ParkingDB() {
    con = mysql_init(nullptr);
}

bool ParkingDB::connect(const std::string& host,
                        const std::string& user,
                        const std::string& pass,
                        const std::string& db,
                        int port)
{
    if (!mysql_real_connect(con,
                            host.c_str(),
                            user.c_str(),
                            pass.c_str(),
                            db.c_str(),
                            port,
                            nullptr,
                            0))
    {
        std::cerr << "Connection error: " << mysql_error(con) << "\n";
        return false;
    }

    std::cout << "Connected successfully!\n";
    return true;
}

bool ParkingDB::exec(const std::string& q) {
    if (mysql_query(con, q.c_str()) != 0) {
        std::cerr << "Query error: " << mysql_error(con) << "\n";
        return false;
    }
    return true;
}

void ParkingDB::createTables() {
    exec(R"sql(
        CREATE TABLE IF NOT EXISTS firme (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nume VARCHAR(50)
        )
    )sql");

    exec(R"sql(
        CREATE TABLE IF NOT EXISTS angajat (
            CNP VARCHAR(20) PRIMARY KEY,
            nume VARCHAR(50),
            numar_inmatriculare VARCHAR(20),
            firma VARCHAR(50)
        )
    )sql");

    exec(R"sql(
        CREATE TABLE IF NOT EXISTS masina (
            nr VARCHAR(20) PRIMARY KEY,
            model VARCHAR(50),
            culoare VARCHAR(20)
        )
    )sql");

    exec(R"sql(
        CREATE TABLE IF NOT EXISTS log (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nr VARCHAR(20),
            nume VARCHAR(50),
            timp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tip VARCHAR(10)
        )
    )sql");

    std::cout << "Tables ready.\n";
}

bool ParkingDB::plateExists(const std::string& nr) {
    std::string q = "SELECT nr FROM masina WHERE nr='" + nr + "' LIMIT 1";

    if (mysql_query(con, q.c_str()) != 0)
        return false;

    MYSQL_RES* res = mysql_store_result(con);

    bool found = (mysql_num_rows(res) > 0);

    mysql_free_result(res);

    return found;
}

void ParkingDB::logEvent(const std::string& nr,
                         const std::string& nume,
                         const std::string& tip)
{
    std::string q =
        "INSERT INTO log(nr, nume, tip) VALUES('" +
        nr + "','" + nume + "','" + tip + "')";

    exec(q);
}

MYSQL* ParkingDB::raw() {
    return con;
}

ParkingDB::~ParkingDB() {
    if (con) mysql_close(con);
}