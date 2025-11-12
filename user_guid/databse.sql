-- Create Database (optional)
CREATE DATABASE IF NOT EXISTS travel_app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE travel_app;

-- ----------------------------
-- Table structure for `admins`
-- ----------------------------
CREATE TABLE IF NOT EXISTS admins (
  id INT NOT NULL AUTO_INCREMENT,
  full_name VARCHAR(255) DEFAULT NULL,
  email VARCHAR(255) DEFAULT NULL UNIQUE,
  contact VARCHAR(20) DEFAULT NULL,
  password TEXT DEFAULT NULL,
  profile_image VARCHAR(255) DEFAULT NULL,
  gender_id INT DEFAULT NULL,
  role VARCHAR(50) DEFAULT NULL,
  address VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for `users`
-- ----------------------------
CREATE TABLE IF NOT EXISTS users (
  id INT NOT NULL AUTO_INCREMENT,
  full_name VARCHAR(255) DEFAULT NULL,
  email VARCHAR(255) DEFAULT NULL UNIQUE,
  contact VARCHAR(20) DEFAULT NULL,
  dob DATE DEFAULT NULL,
  profile_image VARCHAR(255) DEFAULT NULL,
  gender_id INT DEFAULT NULL,
  role VARCHAR(50) DEFAULT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for `buses`
-- ----------------------------
CREATE TABLE IF NOT EXISTS buses (
  id INT NOT NULL AUTO_INCREMENT,
  owner_id INT DEFAULT NULL,
  bus_name VARCHAR(255) DEFAULT NULL,
  bus_type VARCHAR(50) DEFAULT NULL,
  total_seats INT DEFAULT NULL,
  plate_number VARCHAR(50) DEFAULT NULL,
  amenities VARCHAR(255) DEFAULT NULL,
  driver_name VARCHAR(100) DEFAULT NULL,
  driver_contact VARCHAR(20) DEFAULT NULL,
  PRIMARY KEY (id),
  INDEX (owner_id),
  FOREIGN KEY (owner_id) REFERENCES admins(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for `packages`
-- ----------------------------
CREATE TABLE IF NOT EXISTS packages (
  id INT NOT NULL AUTO_INCREMENT,
  owner_id INT DEFAULT NULL,
  title VARCHAR(255) DEFAULT NULL,
  location VARCHAR(255) DEFAULT NULL,
  duration INT DEFAULT NULL,
  price DECIMAL(10,2) DEFAULT NULL,
  inclusions TEXT DEFAULT NULL,
  itinerary TEXT DEFAULT NULL,
  hotel_info VARCHAR(255) DEFAULT NULL,
  image_url VARCHAR(255) DEFAULT NULL,
  bus_id INT DEFAULT NULL,
  boardings VARCHAR(255) DEFAULT NULL,
  start_date DATETIME DEFAULT NULL,
  PRIMARY KEY (id),
  INDEX (owner_id),
  INDEX (bus_id),
  FOREIGN KEY (owner_id) REFERENCES admins(id) ON DELETE SET NULL,
  FOREIGN KEY (bus_id) REFERENCES buses(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for `bookings`
-- ----------------------------
CREATE TABLE IF NOT EXISTS bookings (
  id INT NOT NULL AUTO_INCREMENT,
  user_id INT DEFAULT NULL,
  owner_id INT DEFAULT NULL,
  package_id INT DEFAULT NULL,
  primary_name VARCHAR(100) DEFAULT NULL,
  primary_mobile VARCHAR(15) DEFAULT NULL,
  primary_email VARCHAR(100) DEFAULT NULL,
  primary_gender VARCHAR(10) DEFAULT NULL,
  primary_age INT DEFAULT NULL,
  accompanying_adults INT DEFAULT NULL,
  total_adults INT DEFAULT NULL,
  accompanying_children INT DEFAULT NULL,
  total_child INT DEFAULT NULL,
  boarding_point VARCHAR(100) DEFAULT NULL,
  booking_time DATETIME DEFAULT NULL,
  start_date DATETIME DEFAULT NULL,
  total_price DECIMAL(10,2) DEFAULT NULL,
  razorpay_payment_id VARCHAR(100) DEFAULT NULL,
  payment_type VARCHAR(50) DEFAULT NULL,
  paid_amount DECIMAL(10,2) DEFAULT NULL,
  status VARCHAR(50) DEFAULT NULL,
  cancel_time DATETIME DEFAULT NULL,
  refund_status VARCHAR(50) DEFAULT NULL,
  refund_amount DECIMAL(10,2) DEFAULT NULL,
  refund_time DATETIME DEFAULT NULL,
  PRIMARY KEY (id),
  INDEX (user_id),
  INDEX (owner_id),
  INDEX (package_id),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (owner_id) REFERENCES admins(id) ON DELETE SET NULL,
  FOREIGN KEY (package_id) REFERENCES packages(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for `reviews`
-- ----------------------------
CREATE TABLE IF NOT EXISTS reviews (
  id INT NOT NULL AUTO_INCREMENT,
  package_id INT DEFAULT NULL,
  name VARCHAR(255) DEFAULT NULL,
  rating INT DEFAULT NULL,
  content TEXT DEFAULT NULL,
  approved TINYINT(1) DEFAULT NULL,
  created_at DATETIME DEFAULT NULL,
  PRIMARY KEY (id),
  INDEX (package_id),
  FOREIGN KEY (package_id) REFERENCES packages(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for `seats`
-- ----------------------------
CREATE TABLE IF NOT EXISTS seats (
  id INT NOT NULL AUTO_INCREMENT,
  bus_id INT DEFAULT NULL,
  package_id INT DEFAULT NULL,
  travel_date DATETIME DEFAULT NULL,
  total_seats INT DEFAULT NULL,
  available_seats INT DEFAULT NULL,
  PRIMARY KEY (id),
  INDEX (bus_id),
  INDEX (package_id),
  FOREIGN KEY (bus_id) REFERENCES buses(id) ON DELETE CASCADE,
  FOREIGN KEY (package_id) REFERENCES packages(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------
-- Table structure for `visits`
-- ----------------------------
CREATE TABLE IF NOT EXISTS visits (
  id INT NOT NULL AUTO_INCREMENT,
  ip VARCHAR(45) DEFAULT NULL,
  user_agent TEXT DEFAULT NULL,
  page VARCHAR(255) DEFAULT NULL,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
