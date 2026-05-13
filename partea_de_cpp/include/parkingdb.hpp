#pragma once

#include <string>
#include <mysql/mysql.h>

class ParkingDB {
private:
    MYSQL* con;

public:
    ParkingDB();

    bool connect(const std::string& host,
                 const std::string& user,
                 const std::string& pass,
                 const std::string& db,
                 int port = 0);

    bool exec(const std::string& q);

    void createTables();

    bool plateExists(const std::string& nr);

    void logEvent(const std::string& nr,
                  const std::string& nume,
                  const std::string& tip);

    MYSQL* raw();

    ~ParkingDB();
};