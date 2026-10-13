-- Canonical base schema used by city_onboarding.py for first-run setup.
-- CREATE IF NOT EXISTS leaves existing tables and their data untouched.
-- This file contains schema only: no city rows, sample rows, or DROP/ALTER.

CREATE DATABASE IF NOT EXISTS nriease_guidelines
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

USE nriease_guidelines;

CREATE TABLE IF NOT EXISTS projects (
  project_id BIGINT UNSIGNED NOT NULL,
  project_name VARCHAR(255) NOT NULL,
  city VARCHAR(100) NOT NULL,
  locality VARCHAR(255) NULL,
  property_type VARCHAR(100) NULL,
  project_source VARCHAR(255) NOT NULL DEFAULT 'Square Yards',
  PRIMARY KEY (project_id),
  KEY idx_projects_city_locality (city, locality)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS guideline_sources (
  source_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  city VARCHAR(100) NOT NULL,
  district VARCHAR(100) NOT NULL,
  financial_year VARCHAR(9) NOT NULL,
  file_name VARCHAR(255) NOT NULL,
  source_url VARCHAR(1000) NULL,
  file_sha256 CHAR(64) NULL,
  imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (source_id),
  UNIQUE KEY uq_guideline_source (district, financial_year, file_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS guideline_entries (
  entry_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  source_id BIGINT UNSIGNED NOT NULL,
  printed_page SMALLINT UNSIGNED NOT NULL,
  serial_no INT UNSIGNED NOT NULL,
  urban_local_body VARCHAR(150) NULL,
  sub_area VARCHAR(255) NULL,
  ward VARCHAR(255) NULL,
  tehsil VARCHAR(150) NULL,
  guideline_place VARCHAR(500) NOT NULL,
  normalized_place VARCHAR(500) NOT NULL,
  plot_residential_sqm DECIMAL(16,2) NULL,
  plot_commercial_sqm DECIMAL(16,2) NULL,
  plot_industrial_sqm DECIMAL(16,2) NULL,
  building_residential_rcc_sqm DECIMAL(16,2) NULL,
  building_residential_rbc_sqm DECIMAL(16,2) NULL,
  building_residential_tin_shade_sqm DECIMAL(16,2) NULL,
  building_residential_kaccha_kabelu_sqm DECIMAL(16,2) NULL,
  building_commercial_shop_sqm DECIMAL(16,2) NULL,
  building_commercial_office_sqm DECIMAL(16,2) NULL,
  building_commercial_godown_sqm DECIMAL(16,2) NULL,
  building_multi_residential_sqm DECIMAL(16,2) NULL,
  building_multi_commercial_sqm DECIMAL(16,2) NULL,
  agricultural_irrigated_hectare DECIMAL(18,2) NULL,
  agricultural_unirrigated_hectare DECIMAL(18,2) NULL,
  agricultural_plot_subclause_1_sqm DECIMAL(16,2) NULL,
  agricultural_plot_subclause_2_sqm DECIMAL(16,2) NULL,
  extraction_status ENUM('extracted','reviewed','rejected') NOT NULL DEFAULT 'extracted',
  extraction_note VARCHAR(1000) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (entry_id),
  UNIQUE KEY uq_source_page_serial (source_id, printed_page, serial_no),
  KEY idx_guideline_place (normalized_place(191)),
  KEY idx_guideline_context (urban_local_body, ward(120), tehsil),
  CONSTRAINT fk_entry_source FOREIGN KEY (source_id)
    REFERENCES guideline_sources (source_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS project_guideline_matches (
  match_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  project_id BIGINT UNSIGNED NOT NULL,
  entry_id BIGINT UNSIGNED NOT NULL,
  rate_column_code VARCHAR(64) NOT NULL,
  match_status ENUM('candidate','reviewed','rejected') NOT NULL DEFAULT 'candidate',
  confidence DECIMAL(5,4) NULL,
  rationale VARCHAR(1500) NOT NULL,
  reviewed_by VARCHAR(150) NULL,
  reviewed_at DATETIME NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (match_id),
  UNIQUE KEY uq_project_entry_rate (project_id, entry_id, rate_column_code),
  KEY idx_match_status_project (match_status, project_id),
  CONSTRAINT fk_match_project FOREIGN KEY (project_id)
    REFERENCES projects (project_id) ON DELETE RESTRICT,
  CONSTRAINT fk_match_entry FOREIGN KEY (entry_id)
    REFERENCES guideline_entries (entry_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS financier_reference_sources (
  source_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  financier_name VARCHAR(150) NOT NULL,
  source_title VARCHAR(255) NOT NULL,
  source_type VARCHAR(50) NOT NULL,
  source_url VARCHAR(1000) NULL,
  source_note VARCHAR(500) NULL,
  captured_at DATE NULL,
  PRIMARY KEY (source_id),
  UNIQUE KEY uq_financier_reference_source (financier_name, source_title)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS financier_project_references (
  reference_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  source_id BIGINT UNSIGNED NOT NULL,
  project_id BIGINT UNSIGNED NULL,
  listed_project_name VARCHAR(255) NOT NULL,
  builder_name VARCHAR(255) NULL,
  bank_project_code VARCHAR(100) NULL,
  match_status ENUM('exact','listed','possible','unmatched') NOT NULL DEFAULT 'listed',
  match_note VARCHAR(500) NULL,
  captured_at DATE NULL,
  PRIMARY KEY (reference_id),
  UNIQUE KEY uq_financier_project_reference (source_id, listed_project_name),
  KEY idx_financier_reference_project (project_id),
  CONSTRAINT fk_financier_reference_source FOREIGN KEY (source_id)
    REFERENCES financier_reference_sources (source_id),
  CONSTRAINT fk_financier_reference_project FOREIGN KEY (project_id)
    REFERENCES projects (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS infrastructure_sources (
  source_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  source_key VARCHAR(100) NOT NULL,
  source_type ENUM('webpage','pdf') NOT NULL,
  source_title VARCHAR(255) NOT NULL,
  source_url VARCHAR(1000) NULL,
  file_name VARCHAR(255) NULL,
  fetched_at DATETIME NOT NULL,
  content_sha256 CHAR(64) NULL,
  extracted_content MEDIUMTEXT NULL,
  import_note VARCHAR(1000) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (source_id),
  UNIQUE KEY uq_infrastructure_source_key (source_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS infrastructure_projects (
  infrastructure_project_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  source_id BIGINT UNSIGNED NOT NULL,
  source_item_key CHAR(64) NOT NULL,
  project_name VARCHAR(500) NOT NULL,
  city VARCHAR(100) NOT NULL,
  area_name VARCHAR(500) NULL,
  locality_names JSON NULL,
  scope ENUM('locality','area_based','citywide','unlocated') NOT NULL DEFAULT 'unlocated',
  category VARCHAR(120) NULL,
  program_name VARCHAR(200) NULL,
  status_code ENUM('proposed','tendering','dpr_preparation','awaiting_land_transfer','work_in_progress','completed_reported','unknown') NOT NULL DEFAULT 'unknown',
  status_label VARCHAR(255) NOT NULL DEFAULT 'Status not stated by source',
  description TEXT NULL,
  capacity_value DECIMAL(16,2) NULL,
  capacity_unit VARCHAR(40) NULL,
  source_reference VARCHAR(500) NULL,
  raw_record JSON NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  imported_at DATETIME NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (infrastructure_project_id),
  UNIQUE KEY uq_infrastructure_source_item (source_id, source_item_key),
  KEY idx_infrastructure_city_scope (city, scope, status_code),
  KEY idx_infrastructure_area (area_name(191)),
  CONSTRAINT fk_infrastructure_source FOREIGN KEY (source_id)
    REFERENCES infrastructure_sources (source_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
