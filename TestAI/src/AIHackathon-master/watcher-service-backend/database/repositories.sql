DROP TABLE IF EXISTS `repositories`;
CREATE TABLE `repositories` (
  `id` varchar(36) NOT NULL,
  `name` varchar(255) NOT NULL,
  `path` varchar(500) NOT NULL,
  `is_watching` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `last_change` datetime DEFAULT NULL,
  `total_changes` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `path` (`path`),
  KEY `ix_repositories_last_change` (`last_change`),
  KEY `ix_repositories_is_watching` (`is_watching`),
  KEY `ix_repositories_created_at` (`created_at`),
  KEY `ix_repositories_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;