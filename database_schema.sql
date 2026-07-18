-- Ethara Seat Allocation & Project Mapping System — Database Schema
-- Generated from SQLAlchemy models (models.py)

CREATE TABLE projects (
	id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	description VARCHAR, 
	manager_name VARCHAR, 
	status VARCHAR, 
	created_at DATETIME, 
	PRIMARY KEY (id)
);

CREATE TABLE seats (
	id INTEGER NOT NULL, 
	floor INTEGER NOT NULL, 
	zone VARCHAR NOT NULL, 
	bay VARCHAR NOT NULL, 
	seat_number VARCHAR NOT NULL, 
	status VARCHAR, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_seat_floor_zone_number UNIQUE (floor, zone, seat_number)
);

CREATE TABLE employees (
	id INTEGER NOT NULL, 
	employee_code VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	email VARCHAR NOT NULL, 
	department VARCHAR, 
	role VARCHAR, 
	joining_date DATE NOT NULL, 
	status VARCHAR, 
	project_id INTEGER, 
	seat_allocation_status VARCHAR, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id)
);

CREATE TABLE seat_allocations (
	id INTEGER NOT NULL, 
	employee_id INTEGER NOT NULL, 
	seat_id INTEGER NOT NULL, 
	project_id INTEGER, 
	allocation_status VARCHAR, 
	allocation_date DATETIME, 
	released_date DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id), 
	FOREIGN KEY(seat_id) REFERENCES seats (id), 
	FOREIGN KEY(project_id) REFERENCES projects (id)
);

