CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    userpassword VARCHAR(255),
    role ENUM('developer', 'tester', 'admin') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users (name, email, userpassword, role) 
VALUES
  ('Alice Johnson', 'alice.dev@example.com', 'password123', 'developer'),
  ('Bob Smith', 'bob.tester@example.com', 'testpass456', 'tester'),
  ('Clara Davis', 'clara.admin@example.com', 'admin789', 'admin'),
  ('David Brown', 'david.dev@example.com', 'devpass321', 'developer'),
  ('Eva Green', 'eva.tester@example.com', 'tester654', 'tester');


CREATE TABLE code_changes (
    change_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    change_type ENUM('added', 'modified', 'deleted') NOT NULL,
    previousV varchar(255) NOT NULL,
    currentV varchar(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE ai_results (
    result_id INT AUTO_INCREMENT PRIMARY KEY,
    change_id INT NOT NULL,
    test_cases JSON NOT NULL,
    risk_summary TEXT,
    confidence_score DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (change_id) REFERENCES code_changes(change_id) ON DELETE CASCADE
);

CREATE TABLE feedback (
    feedback_id INT AUTO_INCREMENT PRIMARY KEY,
    result_id INT NOT NULL,
    tester_id INT NOT NULL,
    feedback_text TEXT,
    rating ENUM('useful', 'not_useful', 'partial') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (result_id) REFERENCES ai_results(result_id) ON DELETE CASCADE,
    FOREIGN KEY (tester_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE audit_logs (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(100) NOT NULL,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE test_cases (
    test_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    change_id INT NOT NULL,
    test_description TEXT NOT NULL,
    status ENUM('passed', 'failed', 'skipped') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (change_id) REFERENCES code_changes(change_id) ON DELETE CASCADE
);