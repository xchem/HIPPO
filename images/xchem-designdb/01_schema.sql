-- =========================================================
-- designdb Database Schema
-- =========================================================

-- =========================================================
DROP SCHEMA IF EXISTS designdb CASCADE;
-- =========================================================

-- =========================================================
-- PREREQUISITES & EXTENSIONS
-- =========================================================

CREATE SCHEMA IF NOT EXISTS designdb;
CREATE SCHEMA IF NOT EXISTS rdkit;

CREATE EXTENSION IF NOT EXISTS rdkit WITH SCHEMA rdkit;
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA designdb;

SET search_path TO designdb, rdkit, public;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- =========================================================
-- TABLES (ordered by FK dependencies)
-- =========================================================

CREATE TABLE IF NOT EXISTS designdb.targets (
    id BIGSERIAL PRIMARY KEY, --Internal ID inserted when registering target via Fragalysis
    external_target_id BIGINT, -- ID of this target in the external database (Scarab link)
    target_name TEXT, --Insert from HIPPO codebase. Must be a link to Scarab protein production target
    target_metadata TEXT, -- Not populated by code
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_target UNIQUE (target_name)
);

CREATE TABLE IF NOT EXISTS designdb.compounds (
    id BIGSERIAL PRIMARY KEY,
    compound_inchikey TEXT, -- Populated by RDKit cartridge trigger from compound_smiles (do not insert by code). Maybe insert by the codebase or jupyter. Do we need to write this by code or can be calculated by the cartridge?
    compound_alias TEXT, -- Maybe insert by the codebase.
    compound_smiles TEXT, -- Inserted by the codebase. Trigger populates compound_mol and compound_inchikey. 2D flat SMILES. Is this 2d flat smiles without any stereochemistry? LR - Yes 2D. Looks like designdb function sanitise_smiles does remove stereochemistry - will this be a problem when a user wants to register a design with defined stereochemistry?
    base_compound_id BIGINT REFERENCES designdb.compounds (id) ON DELETE SET NULL, -- Not populated by code
    compound_mol rdkit.mol, -- Populated by RDKit cartridge trigger from compound_smiles (do not insert by code). Originally, maybe insert from codebase and/or Chemicalite/Postgres RDKit cartridge
    compound_pattern_bfp bit(2048), -- Postgres RDkit cartridge can calc this, Chemicalite does, not sure if insert by codebase. Currently seems broken
    compound_morgan_bfp bit(2048), -- Postgres cartridge can't calc this. Must be inserted by codebase, but currently its broken
    compound_metadata TEXT, -- currently Null
    note TEXT,  -- New column
    rdkit_version TEXT, --Can be done by RDkit cartridge
    inchi_version TEXT,  -- Must be done by codebase
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_compound_alias UNIQUE (compound_alias),
    CONSTRAINT uc_compound_inchikey UNIQUE (compound_inchikey),
    CONSTRAINT uc_compound_smiles UNIQUE (compound_smiles)
);

CREATE TABLE IF NOT EXISTS designdb.subsites (
    id BIGSERIAL PRIMARY KEY,
    target_id BIGINT NOT NULL REFERENCES designdb.targets (id) ON DELETE RESTRICT, -- Insert by codebase/notebook
    subsite_name TEXT NOT NULL, -- Insert by codebase/notebook
    subsite_metadata TEXT, -- Not populated by code
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_subsite UNIQUE (target_id, subsite_name)
);

CREATE TABLE IF NOT EXISTS designdb.poses (
    id BIGSERIAL PRIMARY KEY,
    pose_inchikey TEXT, -- Populated by RDKit cartridge trigger from pose_mol (do not insert by code). Originally, nserted by codebase when registering poses? Might be done from pose.mol?
    pose_alias TEXT,
    pose_smiles TEXT, -- Populated by RDKit cartridge trigger from pose_mol (do not insert by code). LR - necessary because will contain defined stereochemistry - should these be canonicalised? Is it done by codebase from pose.mol? Could be done by RDkit cartridge.
    pose_reference INTEGER,
    pose_path TEXT,
    compound_id BIGINT NOT NULL REFERENCES designdb.compounds (id) ON DELETE RESTRICT,
    target_id BIGINT NOT NULL REFERENCES designdb.targets (id) ON DELETE RESTRICT,
    pose_mol rdkit.mol, -- Insert by the codebase. Trigger populates pose_inchikey and pose_smiles. Originally, inserted by the codebase and /or Chemicalite/Postgres RDkit cartridge
    pose_fingerprint INTEGER, --Not sure if it null or actually calcualated somewhere.
    --pose_energy_score REAL, -- LR - this may become redundant once the scores table is implemented
    --pose_distance_score REAL, -- LR - this may become redundant once the scores table is implemented
    --pose_inspiration_score REAL, -- LR - this may become redundant once the scores table is implemented
    pose_metadata TEXT,
    note TEXT,  -- New column
    rdkit_version TEXT, --Can be done by RDkit cartridge
    inchi_version TEXT,  -- Must be done by codebase
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_pose_alias UNIQUE (pose_alias),
    CONSTRAINT uc_pose_path UNIQUE (pose_path)
);

CREATE TABLE IF NOT EXISTS designdb.subsite_tags (
    id BIGSERIAL PRIMARY KEY,
    subsite_id BIGINT NOT NULL REFERENCES designdb.subsites (id) ON DELETE RESTRICT, -- Insert by codebase
    pose_id BIGINT NOT NULL REFERENCES designdb.poses (id) ON DELETE RESTRICT, -- Insert by codebase
    subsite_tag_metadata TEXT, -- Not populated by code
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_subsite_tag UNIQUE (subsite_id, pose_id)
);

-- New table
CREATE TABLE IF NOT EXISTS designdb.pose_methods (
    id BIGSERIAL PRIMARY KEY,
    pose_method_name TEXT,
    pose_method_description TEXT,
    pose_method_version TEXT,
    pose_method_organization TEXT,
    pose_method_link TEXT,
    pose_method_note TEXT,
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now()
);

-- New table
CREATE TABLE IF NOT EXISTS designdb.has_pose_methods (
    pose_id BIGINT NOT NULL REFERENCES designdb.poses (id) ON DELETE CASCADE,
    pose_method_id BIGINT NOT NULL REFERENCES designdb.pose_methods (id) ON DELETE CASCADE,
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (pose_id, pose_method_id)
);

-- New table
CREATE TABLE IF NOT EXISTS designdb.pose_tags (
    id BIGSERIAL PRIMARY KEY,
    pose_tag_name TEXT,
    pose_tag_description TEXT,
    pose_tag_note TEXT,
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now()
);

-- New table
CREATE TABLE IF NOT EXISTS designdb.has_pose_tags (
    pose_id BIGINT NOT NULL REFERENCES designdb.poses (id) ON DELETE CASCADE,
    pose_tag_id BIGINT NOT NULL REFERENCES designdb.pose_tags (id) ON DELETE CASCADE,
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (pose_id, pose_tag_id)
);

CREATE TABLE IF NOT EXISTS designdb.inspirations (
    id BIGSERIAL PRIMARY KEY,
    original_pose_id BIGINT REFERENCES designdb.poses (id) ON DELETE SET NULL, -- Insert by codebase
    derivative_pose_id BIGINT REFERENCES designdb.poses (id) ON DELETE SET NULL, -- Insert by codebase
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_inspiration UNIQUE (original_pose_id, derivative_pose_id)
);

CREATE TABLE IF NOT EXISTS designdb.features (
    id BIGSERIAL PRIMARY KEY,
    feature_family TEXT, -- Insert by codebase
    target_id BIGINT NOT NULL REFERENCES designdb.targets (id) ON DELETE RESTRICT, -- Insert by codebase
    feature_chain_name TEXT, -- Insert by codebase
    feature_residue_name TEXT, -- Insert by codebase
    feature_residue_number INTEGER, -- Insert by codebase
    feature_atom_name TEXT, -- Insert by codebase
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_feature UNIQUE (feature_family, target_id, feature_chain_name, feature_residue_number, feature_residue_name, feature_atom_name)
);

CREATE TABLE IF NOT EXISTS designdb.interactions (
    id BIGSERIAL PRIMARY KEY,
    feature_id BIGINT NOT NULL REFERENCES designdb.features (id) ON DELETE RESTRICT, -- Insert by codebase
    pose_id BIGINT NOT NULL REFERENCES designdb.poses (id) ON DELETE RESTRICT, -- Insert by codebase
    interaction_type TEXT NOT NULL, -- Insert by codebase
    interaction_family TEXT NOT NULL, -- Insert by codebase
    interaction_atom_id TEXT NOT NULL, -- Insert by codebase
    interaction_prot_coord TEXT NOT NULL, -- Insert by codebase. Not populated by ProLIF, needs reviewing
    interaction_lig_coord TEXT NOT NULL, -- Insert by codebase. Not populated by ProLIF, needs reviewing
    interaction_distance REAL NOT NULL, -- Insert by codebase
    interaction_angle REAL, -- Insert by codebase
    interaction_energy REAL, -- Insert by codebase. Not populated by ProLIF, needs reviewing
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_interaction UNIQUE (feature_id, pose_id, interaction_type, interaction_family, interaction_atom_id)
);

-- New table
CREATE TABLE IF NOT EXISTS designdb.compound_tags (
    id BIGSERIAL PRIMARY KEY,
    compound_tag_name TEXT,
    compound_tag_description TEXT,
    compound_tag_note TEXT,
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now()
);

-- New table
CREATE TABLE IF NOT EXISTS designdb.has_compound_tags (
    compound_id BIGINT NOT NULL REFERENCES designdb.compounds (id) ON DELETE CASCADE,
    compound_tag_id BIGINT NOT NULL REFERENCES designdb.compound_tags (id) ON DELETE CASCADE,
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (compound_id, compound_tag_id)
);

-- New table
CREATE TABLE IF NOT EXISTS designdb.enumeration_methods (
    id BIGSERIAL PRIMARY KEY,
    enum_name TEXT,
    enum_description TEXT,
    enum_version TEXT,
    enum_organization TEXT,
    enum_link TEXT,
    enum_note TEXT,
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now()
);

-- New table
CREATE TABLE IF NOT EXISTS designdb.has_enumeration_methods (
    compound_id BIGINT NOT NULL REFERENCES designdb.compounds (id) ON DELETE CASCADE,
    enumeration_method_id BIGINT NOT NULL REFERENCES designdb.enumeration_methods (id) ON DELETE CASCADE,
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (compound_id, enumeration_method_id)
);

-- New table
-- score JSONB: one key per method (use scoring_method.method_name as key).
CREATE TABLE IF NOT EXISTS designdb.scores (
    id BIGSERIAL PRIMARY KEY,
    pose_id BIGINT NOT NULL REFERENCES designdb.poses (id) ON DELETE RESTRICT,
    compound_id BIGINT REFERENCES designdb.compounds (id) ON DELETE SET NULL,
    score JSONB, -- {"vina": {"score": -7.2, "version": "1.0"}, "gnina": {"score": 0.85, "version": "2.1"}}
    note TEXT,
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now()
);

-- New table
CREATE TABLE IF NOT EXISTS designdb.scoring_methods (
    id BIGSERIAL PRIMARY KEY,
    method_name TEXT,
    method_description TEXT,
    method_version TEXT,
    method_organization TEXT,
    method_link TEXT,
    note TEXT,
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS designdb.reactions (
    id BIGSERIAL PRIMARY KEY,
    reaction_type TEXT, -- Insert by codebase/notebook, Synderilla
    product_compound_id BIGINT NOT NULL REFERENCES designdb.compounds (id) ON DELETE RESTRICT, -- Insert by codebase/notebook, Synderilla
    reaction_product_yield REAL, -- Insert by codebase/notebook, Synderilla
    reaction_metadata TEXT, -- Not populated by code
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS designdb.reactants (
    id BIGSERIAL PRIMARY KEY,
    reactant_amount REAL, -- Insert by codebase/notebook, Synderilla
    reaction_id BIGINT NOT NULL REFERENCES designdb.reactions (id) ON DELETE CASCADE, -- Insert by codebase/notebook, Synderilla
    compound_id BIGINT NOT NULL REFERENCES designdb.compounds (id) ON DELETE RESTRICT, -- Insert by codebase/notebook, Synderilla
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_reactant UNIQUE (reaction_id, compound_id)
);

CREATE TABLE IF NOT EXISTS designdb.quotes (
    id BIGSERIAL PRIMARY KEY,
    quote_smiles TEXT,
    quote_amount REAL,
    quote_supplier TEXT,
    quote_catalogue TEXT, -- Catalogue (there are null values, plus BB, Full stock etc.)
    quote_entry TEXT, -- This the catalogue number (supplier id)
    quote_lead_time INTEGER, -- Days, weeks?
    quote_price REAL,
    quote_currency TEXT,
    quote_purity REAL, -- Not percentage (e.g. 0.99)
    quote_date TEXT,
    compound_id BIGINT REFERENCES designdb.compounds (id) ON DELETE SET NULL, --Quote compound originally, mapped with compound_id
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_quote UNIQUE (quote_amount, quote_supplier, quote_catalogue, quote_entry)
);

CREATE TABLE IF NOT EXISTS designdb.scaffolds (
    id BIGSERIAL PRIMARY KEY,
    base_compound_id BIGINT REFERENCES designdb.compounds (id) ON DELETE SET NULL, -- Insert by codebase
    superstructure_compound_id BIGINT REFERENCES designdb.compounds (id) ON DELETE SET NULL, -- Insert by codebase
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_scaffold UNIQUE (base_compound_id, superstructure_compound_id)
);

CREATE TABLE IF NOT EXISTS designdb.routes (
    id BIGSERIAL PRIMARY KEY,
    product_compound_id BIGINT NOT NULL REFERENCES designdb.compounds (id) ON DELETE RESTRICT, -- Insert by codebase/notebook, Synderilla
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS designdb.components (
    id BIGSERIAL PRIMARY KEY,
    route_id BIGINT NOT NULL REFERENCES designdb.routes (id) ON DELETE RESTRICT, -- Insert by codebase/notebook, Synderilla
    component_type INTEGER, -- Insert by codebase/notebook, Synderilla-- 
    component_ref INTEGER, -- Insert by codebase/notebook, Synderilla
    component_amount REAL, -- Insert by codebase/notebook, Synderilla
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_component UNIQUE (route_id, component_ref, component_type)
);

-- Replaced table with individual tag tables
-- CREATE TABLE IF NOT EXISTS designdb.tags (
--     id BIGSERIAL PRIMARY KEY,
--     tag_name TEXT, -- Insert by codebase
--     tag_description TEXT, -- New column
--     note TEXT, -- New column
--     -- compound_id BIGINT REFERENCES designdb.compounds (id) ON DELETE SET NULL, -- Insert by codebase, need to be removed, change in code needed
--     -- pose_id BIGINT REFERENCES designdb.poses (id) ON DELETE SET NULL, -- Insert by codebase, need to be removed, change in code needed
--     created_on TIMESTAMPTZ DEFAULT now(),
--     updated_on TIMESTAMPTZ DEFAULT now()
--     -- CONSTRAINT uc_tag_compound UNIQUE (tag_name, compound_id),
--     -- CONSTRAINT uc_tag_pose UNIQUE (tag_name, pose_id)
-- );


-- =========================================================
-- AUDIT TABLES
-- =========================================================

-- Event audit for quotes (tracks INSERT/UPDATE/DELETE for data load change tracking)
CREATE TABLE IF NOT EXISTS designdb.quotes_event_audit (
    audit_pk BIGSERIAL PRIMARY KEY,
    id BIGINT NOT NULL,
    operation CHAR(1) NOT NULL, -- 'I'|'U'|'D'
    old_values JSONB,
    new_values JSONB,
    changed_by TEXT,
    changed_at TIMESTAMPTZ DEFAULT now()
);

-- Event audit for pose_tags
CREATE TABLE IF NOT EXISTS designdb.pose_tags_event_audit (
    audit_pk BIGSERIAL PRIMARY KEY,
    id BIGINT NOT NULL,
    operation CHAR(1) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    changed_by TEXT,
    changed_at TIMESTAMPTZ DEFAULT now()
);

-- Event audit for compound_tags
CREATE TABLE IF NOT EXISTS designdb.compound_tags_event_audit (
    audit_pk BIGSERIAL PRIMARY KEY,
    id BIGINT NOT NULL,
    operation CHAR(1) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    changed_by TEXT,
    changed_at TIMESTAMPTZ DEFAULT now()
);

-- Event audit for pose_methods
CREATE TABLE IF NOT EXISTS designdb.pose_methods_event_audit (
    audit_pk BIGSERIAL PRIMARY KEY,
    id BIGINT NOT NULL,
    operation CHAR(1) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    changed_by TEXT,
    changed_at TIMESTAMPTZ DEFAULT now()
);

-- Event audit for enumeration_methods
CREATE TABLE IF NOT EXISTS designdb.enumeration_methods_event_audit (
    audit_pk BIGSERIAL PRIMARY KEY,
    id BIGINT NOT NULL,
    operation CHAR(1) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    changed_by TEXT,
    changed_at TIMESTAMPTZ DEFAULT now()
);

-- Event audit for scoring_methods
CREATE TABLE IF NOT EXISTS designdb.scoring_methods_event_audit (
    audit_pk BIGSERIAL PRIMARY KEY,
    id BIGINT NOT NULL,
    operation CHAR(1) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    changed_by TEXT,
    changed_at TIMESTAMPTZ DEFAULT now()
);

-- =========================================================
-- INDEXES
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_target_name ON designdb.targets(target_name);
CREATE INDEX IF NOT EXISTS idx_target_created ON designdb.targets(created_on);

CREATE INDEX IF NOT EXISTS idx_scoring_method_name ON designdb.scoring_methods(method_name);
CREATE INDEX IF NOT EXISTS idx_scoring_method_created ON designdb.scoring_methods(created_on);

CREATE INDEX IF NOT EXISTS idx_enumeration_method_name ON designdb.enumeration_methods(enum_name);
CREATE INDEX IF NOT EXISTS idx_enumeration_method_created ON designdb.enumeration_methods(created_on);

CREATE INDEX IF NOT EXISTS idx_pose_method_name ON designdb.pose_methods(pose_method_name);
CREATE INDEX IF NOT EXISTS idx_pose_method_created ON designdb.pose_methods(created_on);

CREATE INDEX IF NOT EXISTS idx_compound_base_compound_id ON designdb.compounds(base_compound_id);
CREATE INDEX IF NOT EXISTS idx_compound_inchikey ON designdb.compounds(compound_inchikey);
CREATE INDEX IF NOT EXISTS idx_compound_smiles ON designdb.compounds(compound_smiles);
CREATE INDEX IF NOT EXISTS idx_compound_created ON designdb.compounds(created_on);

CREATE INDEX IF NOT EXISTS idx_feature_target_id ON designdb.features(target_id);
CREATE INDEX IF NOT EXISTS idx_feature_created ON designdb.features(created_on);

CREATE INDEX IF NOT EXISTS idx_route_product_compound_id ON designdb.routes(product_compound_id);
CREATE INDEX IF NOT EXISTS idx_route_created ON designdb.routes(created_on);

CREATE INDEX IF NOT EXISTS idx_reaction_product_compound_id ON designdb.reactions(product_compound_id);
CREATE INDEX IF NOT EXISTS idx_reaction_created ON designdb.reactions(created_on);

CREATE INDEX IF NOT EXISTS idx_pose_compound_id ON designdb.poses(compound_id);
CREATE INDEX IF NOT EXISTS idx_pose_target_id ON designdb.poses(target_id);
CREATE INDEX IF NOT EXISTS idx_pose_path ON designdb.poses(pose_path);
CREATE INDEX IF NOT EXISTS idx_pose_created ON designdb.poses(created_on);

CREATE INDEX IF NOT EXISTS idx_scores_pose_id ON designdb.scores(pose_id);
CREATE INDEX IF NOT EXISTS idx_scores_compound_id ON designdb.scores(compound_id);
CREATE INDEX IF NOT EXISTS idx_scores_pose_id_compound_id ON designdb.scores(pose_id, compound_id);
CREATE INDEX IF NOT EXISTS idx_scores_created ON designdb.scores(created_on);
CREATE INDEX IF NOT EXISTS idx_scores_score_gin ON designdb.scores USING GIN (score);

CREATE INDEX IF NOT EXISTS idx_subsite_target_id ON designdb.subsites(target_id);
CREATE INDEX IF NOT EXISTS idx_subsite_created ON designdb.subsites(created_on);

CREATE INDEX IF NOT EXISTS idx_component_route_id ON designdb.components(route_id);
CREATE INDEX IF NOT EXISTS idx_component_created ON designdb.components(created_on);

CREATE INDEX IF NOT EXISTS idx_inspiration_original_pose_id ON designdb.inspirations(original_pose_id);
CREATE INDEX IF NOT EXISTS idx_inspiration_derivative_pose_id ON designdb.inspirations(derivative_pose_id);
CREATE INDEX IF NOT EXISTS idx_inspiration_created ON designdb.inspirations(created_on);

CREATE INDEX IF NOT EXISTS idx_interaction_feature_id ON designdb.interactions(feature_id);
CREATE INDEX IF NOT EXISTS idx_interaction_pose_id ON designdb.interactions(pose_id);
CREATE INDEX IF NOT EXISTS idx_interaction_created ON designdb.interactions(created_on);

CREATE INDEX IF NOT EXISTS idx_quote_compound_id ON designdb.quotes(compound_id);
CREATE INDEX IF NOT EXISTS idx_quote_created ON designdb.quotes(created_on);

-- =========================================================
-- AUDIT INDEXES
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_quotes_event_audit_id ON designdb.quotes_event_audit(id);
CREATE INDEX IF NOT EXISTS idx_quotes_event_audit_operation ON designdb.quotes_event_audit(operation);
CREATE INDEX IF NOT EXISTS idx_quotes_event_audit_changed_at ON designdb.quotes_event_audit(changed_at);
CREATE INDEX IF NOT EXISTS idx_quotes_event_audit_changed_by ON designdb.quotes_event_audit(changed_by);
CREATE INDEX IF NOT EXISTS idx_quotes_event_audit_old_gin ON designdb.quotes_event_audit USING GIN (old_values);
CREATE INDEX IF NOT EXISTS idx_quotes_event_audit_new_gin ON designdb.quotes_event_audit USING GIN (new_values);
CREATE INDEX IF NOT EXISTS idx_quotes_event_audit_id_changed ON designdb.quotes_event_audit(id, changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_pose_tags_event_audit_id ON designdb.pose_tags_event_audit(id);
CREATE INDEX IF NOT EXISTS idx_pose_tags_event_audit_operation ON designdb.pose_tags_event_audit(operation);
CREATE INDEX IF NOT EXISTS idx_pose_tags_event_audit_changed_at ON designdb.pose_tags_event_audit(changed_at);
CREATE INDEX IF NOT EXISTS idx_pose_tags_event_audit_old_gin ON designdb.pose_tags_event_audit USING GIN (old_values);
CREATE INDEX IF NOT EXISTS idx_pose_tags_event_audit_new_gin ON designdb.pose_tags_event_audit USING GIN (new_values);
CREATE INDEX IF NOT EXISTS idx_pose_tags_event_audit_id_changed ON designdb.pose_tags_event_audit(id, changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_compound_tags_event_audit_id ON designdb.compound_tags_event_audit(id);
CREATE INDEX IF NOT EXISTS idx_compound_tags_event_audit_operation ON designdb.compound_tags_event_audit(operation);
CREATE INDEX IF NOT EXISTS idx_compound_tags_event_audit_changed_at ON designdb.compound_tags_event_audit(changed_at);
CREATE INDEX IF NOT EXISTS idx_compound_tags_event_audit_old_gin ON designdb.compound_tags_event_audit USING GIN (old_values);
CREATE INDEX IF NOT EXISTS idx_compound_tags_event_audit_new_gin ON designdb.compound_tags_event_audit USING GIN (new_values);
CREATE INDEX IF NOT EXISTS idx_compound_tags_event_audit_id_changed ON designdb.compound_tags_event_audit(id, changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_pose_methods_event_audit_id ON designdb.pose_methods_event_audit(id);
CREATE INDEX IF NOT EXISTS idx_pose_methods_event_audit_operation ON designdb.pose_methods_event_audit(operation);
CREATE INDEX IF NOT EXISTS idx_pose_methods_event_audit_changed_at ON designdb.pose_methods_event_audit(changed_at);
CREATE INDEX IF NOT EXISTS idx_pose_methods_event_audit_old_gin ON designdb.pose_methods_event_audit USING GIN (old_values);
CREATE INDEX IF NOT EXISTS idx_pose_methods_event_audit_new_gin ON designdb.pose_methods_event_audit USING GIN (new_values);
CREATE INDEX IF NOT EXISTS idx_pose_methods_event_audit_id_changed ON designdb.pose_methods_event_audit(id, changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_enumeration_methods_event_audit_id ON designdb.enumeration_methods_event_audit(id);
CREATE INDEX IF NOT EXISTS idx_enumeration_methods_event_audit_operation ON designdb.enumeration_methods_event_audit(operation);
CREATE INDEX IF NOT EXISTS idx_enumeration_methods_event_audit_changed_at ON designdb.enumeration_methods_event_audit(changed_at);
CREATE INDEX IF NOT EXISTS idx_enumeration_methods_event_audit_old_gin ON designdb.enumeration_methods_event_audit USING GIN (old_values);
CREATE INDEX IF NOT EXISTS idx_enumeration_methods_event_audit_new_gin ON designdb.enumeration_methods_event_audit USING GIN (new_values);
CREATE INDEX IF NOT EXISTS idx_enumeration_methods_event_audit_id_changed ON designdb.enumeration_methods_event_audit(id, changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_scoring_methods_event_audit_id ON designdb.scoring_methods_event_audit(id);
CREATE INDEX IF NOT EXISTS idx_scoring_methods_event_audit_operation ON designdb.scoring_methods_event_audit(operation);
CREATE INDEX IF NOT EXISTS idx_scoring_methods_event_audit_changed_at ON designdb.scoring_methods_event_audit(changed_at);
CREATE INDEX IF NOT EXISTS idx_scoring_methods_event_audit_old_gin ON designdb.scoring_methods_event_audit USING GIN (old_values);
CREATE INDEX IF NOT EXISTS idx_scoring_methods_event_audit_new_gin ON designdb.scoring_methods_event_audit USING GIN (new_values);
CREATE INDEX IF NOT EXISTS idx_scoring_methods_event_audit_id_changed ON designdb.scoring_methods_event_audit(id, changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_reactant_reaction_id ON designdb.reactants(reaction_id);
CREATE INDEX IF NOT EXISTS idx_reactant_compound_id ON designdb.reactants(compound_id);
CREATE INDEX IF NOT EXISTS idx_reactant_created ON designdb.reactants(created_on);

CREATE INDEX IF NOT EXISTS idx_scaffold_base_compound_id ON designdb.scaffolds(base_compound_id);
CREATE INDEX IF NOT EXISTS idx_scaffold_superstructure_compound_id ON designdb.scaffolds(superstructure_compound_id);
CREATE INDEX IF NOT EXISTS idx_scaffold_created ON designdb.scaffolds(created_on);

CREATE INDEX IF NOT EXISTS idx_subsite_tag_subsite_id ON designdb.subsite_tags(subsite_id);
CREATE INDEX IF NOT EXISTS idx_subsite_tag_pose_id ON designdb.subsite_tags(pose_id);
CREATE INDEX IF NOT EXISTS idx_subsite_tag_created ON designdb.subsite_tags(created_on);

-- Removed due to replaced tables
-- CREATE INDEX IF NOT EXISTS idx_tag_compound ON designdb.tags(tag_compound);
-- CREATE INDEX IF NOT EXISTS idx_tag_pose ON designdb.tags(tag_pose);
-- CREATE INDEX IF NOT EXISTS idx_tag_created ON designdb.tags(created_on);

CREATE INDEX IF NOT EXISTS idx_pose_tag_created ON designdb.pose_tags(created_on);
CREATE INDEX IF NOT EXISTS idx_compound_tag_created ON designdb.compound_tags(created_on);

CREATE INDEX IF NOT EXISTS idx_has_pose_methods_pose_method_id ON designdb.has_pose_methods(pose_method_id);
CREATE INDEX IF NOT EXISTS idx_has_pose_methods_created ON designdb.has_pose_methods(created_on);

CREATE INDEX IF NOT EXISTS idx_has_pose_tag_pose_tag_id ON designdb.has_pose_tags(pose_tag_id);
CREATE INDEX IF NOT EXISTS idx_has_pose_tag_created ON designdb.has_pose_tags(created_on);

CREATE INDEX IF NOT EXISTS idx_has_enumeration_methods_enumeration_method_id ON designdb.has_enumeration_methods(enumeration_method_id);
CREATE INDEX IF NOT EXISTS idx_has_enumeration_methods_created ON designdb.has_enumeration_methods(created_on);

CREATE INDEX IF NOT EXISTS idx_has_compound_tag_compound_tag_id ON designdb.has_compound_tags(compound_tag_id);
CREATE INDEX IF NOT EXISTS idx_has_compound_tag_created ON designdb.has_compound_tags(created_on);

-- =========================================================
-- MATERIALIZED VIEWS
-- =========================================================
-- designdb.scores_per_pose_pivoted_mv: score_id, pose_id, compound_id + one column per
-- (method_name, method_version) from scoring_methods, filled from scores.score JSONB. Dymanically re-generated from scores table when new method added

-- =========================================================
-- VIEWS
-- =========================================================

-- Shows quote updates captured via designdb.quotes_event_audit
CREATE OR REPLACE VIEW designdb.quotes_price_changes_v AS
SELECT
  a.id AS quote_id,
  (NULLIF(COALESCE(a.new_values->>'compound_id', a.old_values->>'compound_id'), ''))::BIGINT AS compound_id,
  COALESCE(a.new_values->>'quote_smiles', a.old_values->>'quote_smiles') AS quote_smiles,
  (NULLIF(COALESCE(a.new_values->>'quote_amount', a.old_values->>'quote_amount'), ''))::DOUBLE PRECISION AS quote_amount,
  COALESCE(a.new_values->>'quote_supplier', a.old_values->>'quote_supplier') AS quote_supplier,
  COALESCE(a.new_values->>'quote_catalogue', a.old_values->>'quote_catalogue') AS quote_catalogue,
  COALESCE(a.new_values->>'quote_entry', a.old_values->>'quote_entry') AS quote_entry,
  (NULLIF(a.old_values->>'quote_price', ''))::DOUBLE PRECISION AS quote_price_old,
  (NULLIF(a.new_values->>'quote_price', ''))::DOUBLE PRECISION AS quote_price_new,
  COALESCE(a.new_values->>'quote_currency', a.old_values->>'quote_currency') AS quote_currency,
  (NULLIF(COALESCE(a.new_values->>'quote_purity', a.old_values->>'quote_purity'), ''))::DOUBLE PRECISION AS quote_purity,
  a.changed_at
FROM designdb.quotes_event_audit a
WHERE a.operation = 'U';

-- Pose tags: UPDATE events with old/new name, description, note.
CREATE OR REPLACE VIEW designdb.pose_tags_changes_v AS
SELECT
  a.id AS pose_tag_id,
  a.old_values->>'pose_tag_name' AS pose_tag_name_old,
  a.new_values->>'pose_tag_name' AS pose_tag_name_new,
  a.old_values->>'pose_tag_description' AS pose_tag_description_old,
  a.new_values->>'pose_tag_description' AS pose_tag_description_new,
  a.old_values->>'pose_tag_note' AS pose_tag_note_old,
  a.new_values->>'pose_tag_note' AS pose_tag_note_new,
  a.changed_by,
  a.changed_at
FROM designdb.pose_tags_event_audit a
WHERE a.operation = 'U';

-- Compound tags: UPDATE events with old/new name, description, note.
CREATE OR REPLACE VIEW designdb.compound_tags_changes_v AS
SELECT
  a.id AS compound_tag_id,
  a.old_values->>'compound_tag_name' AS compound_tag_name_old,
  a.new_values->>'compound_tag_name' AS compound_tag_name_new,
  a.old_values->>'compound_tag_description' AS compound_tag_description_old,
  a.new_values->>'compound_tag_description' AS compound_tag_description_new,
  a.old_values->>'compound_tag_note' AS compound_tag_note_old,
  a.new_values->>'compound_tag_note' AS compound_tag_note_new,
  a.changed_by,
  a.changed_at
FROM designdb.compound_tags_event_audit a
WHERE a.operation = 'U';

-- Pose methods: UPDATE events with old/new name, description, version, etc.
CREATE OR REPLACE VIEW designdb.pose_methods_changes_v AS
SELECT
  a.id AS pose_method_id,
  a.old_values->>'pose_method_name' AS pose_method_name_old,
  a.new_values->>'pose_method_name' AS pose_method_name_new,
  a.old_values->>'pose_method_description' AS pose_method_description_old,
  a.new_values->>'pose_method_description' AS pose_method_description_new,
  a.old_values->>'pose_method_version' AS pose_method_version_old,
  a.new_values->>'pose_method_version' AS pose_method_version_new,
  a.changed_by,
  a.changed_at
FROM designdb.pose_methods_event_audit a
WHERE a.operation = 'U';

-- Enumeration methods: UPDATE events with old/new name, description, version, etc.
CREATE OR REPLACE VIEW designdb.enumeration_methods_changes_v AS
SELECT
  a.id AS enumeration_method_id,
  a.old_values->>'enum_name' AS enum_name_old,
  a.new_values->>'enum_name' AS enum_name_new,
  a.old_values->>'enum_description' AS enum_description_old,
  a.new_values->>'enum_description' AS enum_description_new,
  a.old_values->>'enum_version' AS enum_version_old,
  a.new_values->>'enum_version' AS enum_version_new,
  a.changed_by,
  a.changed_at
FROM designdb.enumeration_methods_event_audit a
WHERE a.operation = 'U';

-- Scoring methods: UPDATE events with old/new name, description, version, etc.
CREATE OR REPLACE VIEW designdb.scoring_methods_changes_v AS
SELECT
  a.id AS scoring_method_id,
  a.old_values->>'method_name' AS method_name_old,
  a.new_values->>'method_name' AS method_name_new,
  a.old_values->>'method_description' AS method_description_old,
  a.new_values->>'method_description' AS method_description_new,
  a.old_values->>'method_version' AS method_version_old,
  a.new_values->>'method_version' AS method_version_new,
  a.changed_by,
  a.changed_at
FROM designdb.scoring_methods_event_audit a
WHERE a.operation = 'U';

-- =========================================================
-- FUNCTIONS
-- =========================================================

-- =========================================================
-- RDKIT CARTRIDGE – COMPOUND WRAPPERS
-- =========================================================
-- Schema-qualified wrappers for RDKit mol_from_smiles, mol_to_smiles, mol_inchikey (used by compound, pose, and quote triggers).

CREATE OR REPLACE FUNCTION designdb.mol_from_smiles(smiles TEXT) RETURNS rdkit.mol
  LANGUAGE SQL AS $$ SELECT rdkit.mol_from_smiles(smiles::cstring); $$;

CREATE OR REPLACE FUNCTION designdb.mol_to_smiles(m rdkit.mol) RETURNS text
  LANGUAGE SQL AS $$ SELECT rdkit.mol_to_smiles(m); $$;

CREATE OR REPLACE FUNCTION designdb.mol_to_inchikey(m rdkit.mol) RETURNS text
  LANGUAGE SQL AS $$ SELECT rdkit.mol_inchikey(m); $$;

-- =========================================================
-- RDKIT CARTRIDGE – COMPOUND TRIGGER
-- =========================================================
-- Input: compound_smiles (inserted by application). Populates compound_mol and compound_inchikey.

CREATE OR REPLACE FUNCTION designdb.populate_compound_cartridge_from_smiles()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_mol rdkit.mol;
BEGIN
  IF NEW.compound_smiles IS NOT NULL THEN
    BEGIN
      v_mol := designdb.mol_from_smiles(NEW.compound_smiles);
      IF v_mol IS NOT NULL THEN
        NEW.compound_mol := v_mol;
        NEW.compound_inchikey := designdb.mol_to_inchikey(v_mol);
      END IF;
    EXCEPTION WHEN OTHERS THEN
      NULL;
    END;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_populate_compound_cartridge_from_smiles ON designdb.compounds;
CREATE TRIGGER trg_populate_compound_cartridge_from_smiles
  BEFORE INSERT OR UPDATE OF compound_smiles ON designdb.compounds
  FOR EACH ROW
  EXECUTE FUNCTION designdb.populate_compound_cartridge_from_smiles();

-- =========================================================
-- RDKIT CARTRIDGE – POSE TRIGGER
-- =========================================================
-- Input: pose_mol (inserted by application). Populates pose_inchikey and pose_smiles.

CREATE OR REPLACE FUNCTION designdb.populate_pose_cartridge_from_mol()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.pose_mol IS NOT NULL THEN
    BEGIN
      NEW.pose_smiles := designdb.mol_to_smiles(NEW.pose_mol);
      NEW.pose_inchikey := designdb.mol_to_inchikey(NEW.pose_mol);
    EXCEPTION WHEN OTHERS THEN
      NULL;
    END;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_populate_pose_cartridge_from_mol ON designdb.poses;
CREATE TRIGGER trg_populate_pose_cartridge_from_mol
  BEFORE INSERT OR UPDATE OF pose_mol ON designdb.poses
  FOR EACH ROW
  EXECUTE FUNCTION designdb.populate_pose_cartridge_from_mol();

-- =========================================================
-- (Re)creates materialized view designdb.scores_per_pose_pivoted_mv with columns from scoring_method.
-- Columns: score_id, pose_id, compound_id, then one JSONB column per (method_name, method_version).
-- Value in column: if score is numeric then JSONB number, if text then JSONB string (so numeric stays numeric, text stays text).
CREATE OR REPLACE FUNCTION designdb.create_scores_per_pose_pivoted_mv()
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  select_qry text;
  col text;
  method_rec record;
  score_txt text;
  value_expr text;
  numeric_pat text := '^\-?[0-9]*\.?[0-9]+([eE][\-+]?[0-9]+)?$';
BEGIN
  select_qry := 'SELECT s.id AS score_id, s.pose_id, s.compound_id';
  FOR method_rec IN
    SELECT m.method_name, m.method_version
    FROM designdb.scoring_methods m
    ORDER BY m.id
  LOOP
    col := regexp_replace(
      trim(method_rec.method_name) || '_' || coalesce(
        replace(replace(trim(coalesce(method_rec.method_version, '')), ' ', '_'), '.', '_'),
        ''
      ),
      '[^a-zA-Z0-9_]', '_', 'g'
    );
    IF col <> '' AND col <> '_' THEN
      col := quote_ident(col);
      score_txt := '(s.score->' || quote_literal(trim(method_rec.method_name)) || '->>' || quote_literal('score') || ')';
      value_expr := '(CASE WHEN ' || score_txt || ' IS NOT NULL AND ' || score_txt || ' ~ ' || quote_literal(numeric_pat)
        || ' THEN to_jsonb((' || score_txt || ')::numeric) ELSE to_jsonb(' || score_txt || ') END)';
      select_qry := select_qry || ', (CASE WHEN s.score ? ' || quote_literal(trim(method_rec.method_name))
        || ' AND (s.score->' || quote_literal(trim(method_rec.method_name)) || '->>' || quote_literal('version')
        || ') IS NOT DISTINCT FROM ' || quote_nullable(method_rec.method_version)
        || ' THEN ' || value_expr || ' END) AS ' || col;
    END IF;
  END LOOP;
  select_qry := select_qry || ' FROM designdb.scores s WHERE s.score IS NOT NULL';
  EXECUTE 'DROP MATERIALIZED VIEW IF EXISTS designdb.scores_per_pose_pivoted_mv CASCADE';
  EXECUTE 'CREATE MATERIALIZED VIEW designdb.scores_per_pose_pivoted_mv AS ' || select_qry;
END;
$$;

CREATE OR REPLACE FUNCTION designdb.trg_recreate_scores_pivoted_mv()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  PERFORM designdb.create_scores_per_pose_pivoted_mv();
  RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION designdb.refresh_scores_per_pose_pivoted_mv()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  REFRESH MATERIALIZED VIEW designdb.scores_per_pose_pivoted_mv;
  RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION designdb.update_updated_on()
RETURNS trigger AS $$
BEGIN
    NEW.updated_on = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =========================================================
-- AUDIT FUNCTIONS
-- =========================================================

-- Event audit trigger: records INSERT/UPDATE/DELETE to an audit table with JSONB old/new values.
-- TG_ARGV[0]=audit_table, [1]=pk_column, [2]=excluded_columns (comma-sep), [3]=binary_columns (comma-sep, hashed as sha256:hex).
CREATE OR REPLACE FUNCTION designdb.event_audit_trigger()
RETURNS trigger AS
$$
DECLARE
    v_audit_table TEXT := TG_ARGV[0];
    v_pk_col TEXT := TG_ARGV[1];
    v_excluded TEXT := COALESCE(TG_ARGV[2], '');
    v_bincols TEXT := COALESCE(TG_ARGV[3], '');
    v_excluded_arr TEXT[];
    v_bincols_arr TEXT[];
    v_changed_by TEXT := COALESCE(current_setting('app.current_user', true), current_user);
    v_old_json JSONB;
    v_new_json JSONB;
    v_record_pk TEXT;
    v_bin_hash TEXT;
    v_col TEXT;
BEGIN
    IF v_excluded = '' THEN
        v_excluded_arr := ARRAY[]::text[];
    ELSE
        v_excluded_arr := ARRAY(SELECT trim(x) FROM regexp_split_to_table(v_excluded, ',') AS x);
    END IF;

    IF v_bincols = '' THEN
        v_bincols_arr := ARRAY[]::text[];
    ELSE
        v_bincols_arr := ARRAY(SELECT trim(x) FROM regexp_split_to_table(v_bincols, ',') AS x);
    END IF;

    IF TG_OP = 'INSERT' THEN
        v_old_json := NULL;
        v_new_json := to_jsonb(NEW);
    ELSIF TG_OP = 'DELETE' THEN
        v_old_json := to_jsonb(OLD);
        v_new_json := NULL;
    ELSE
        IF to_jsonb(OLD) IS NOT DISTINCT FROM to_jsonb(NEW) THEN
            RETURN NEW;
        END IF;
        v_old_json := to_jsonb(OLD);
        v_new_json := to_jsonb(NEW);
    END IF;

    FOREACH v_col IN ARRAY v_excluded_arr LOOP
        IF v_old_json IS NOT NULL THEN v_old_json := v_old_json - v_col; END IF;
        IF v_new_json IS NOT NULL THEN v_new_json := v_new_json - v_col; END IF;
    END LOOP;

    FOREACH v_col IN ARRAY v_bincols_arr LOOP
        IF v_old_json IS NOT NULL AND v_old_json ? v_col THEN
            BEGIN
                EXECUTE format('SELECT CASE WHEN ($1).%I IS NULL THEN NULL ELSE encode(digest(($1).%I::bytea, ''sha256''), ''hex'') END', v_col, v_col)
                USING OLD INTO v_bin_hash;
                IF v_bin_hash IS NOT NULL THEN
                    v_old_json := jsonb_set(v_old_json, ARRAY[v_col], to_jsonb('sha256:' || v_bin_hash));
                ELSE
                    v_old_json := v_old_json - v_col;
                END IF;
            EXCEPTION WHEN others THEN
                v_old_json := v_old_json - v_col;
            END;
        END IF;
        IF v_new_json IS NOT NULL AND v_new_json ? v_col THEN
            BEGIN
                EXECUTE format('SELECT CASE WHEN ($1).%I IS NULL THEN NULL ELSE encode(digest(($1).%I::bytea, ''sha256''), ''hex'') END', v_col, v_col)
                USING NEW INTO v_bin_hash;
                IF v_bin_hash IS NOT NULL THEN
                    v_new_json := jsonb_set(v_new_json, ARRAY[v_col], to_jsonb('sha256:' || v_bin_hash));
                ELSE
                    v_new_json := v_new_json - v_col;
                END IF;
            EXCEPTION WHEN others THEN
                v_new_json := v_new_json - v_col;
            END;
        END IF;
    END LOOP;

    IF TG_OP = 'DELETE' THEN
        EXECUTE format('SELECT ($1).%I::text', v_pk_col) USING OLD INTO v_record_pk;
    ELSE
        EXECUTE format('SELECT ($1).%I::text', v_pk_col) USING NEW INTO v_record_pk;
    END IF;

    EXECUTE format('INSERT INTO %s (%s, operation, old_values, new_values, changed_by, changed_at) VALUES ($1,$2,$3,$4,$5,NOW())', v_audit_table, v_pk_col)
    USING v_record_pk::BIGINT, TG_OP::CHAR, v_old_json, v_new_json, v_changed_by;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql VOLATILE;

-- =========================================================
-- TRIGGERS (updated_on)
-- =========================================================

DROP TRIGGER IF EXISTS trg_target_updated_on ON designdb.targets;
CREATE TRIGGER trg_target_updated_on BEFORE UPDATE ON designdb.targets FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_scoring_method_updated_on ON designdb.scoring_methods;
CREATE TRIGGER trg_scoring_method_updated_on BEFORE UPDATE ON designdb.scoring_methods FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_scoring_method_recreate_pivoted_mv ON designdb.scoring_methods;
CREATE TRIGGER trg_scoring_method_recreate_pivoted_mv
  AFTER INSERT OR UPDATE OR DELETE ON designdb.scoring_methods
  FOR EACH STATEMENT EXECUTE FUNCTION designdb.trg_recreate_scores_pivoted_mv();

DROP TRIGGER IF EXISTS trg_enumeration_method_updated_on ON designdb.enumeration_methods;
CREATE TRIGGER trg_enumeration_method_updated_on BEFORE UPDATE ON designdb.enumeration_methods FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_pose_method_updated_on ON designdb.pose_methods;
CREATE TRIGGER trg_pose_method_updated_on BEFORE UPDATE ON designdb.pose_methods FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_compound_updated_on ON designdb.compounds;
CREATE TRIGGER trg_compound_updated_on BEFORE UPDATE ON designdb.compounds FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_feature_updated_on ON designdb.features;
CREATE TRIGGER trg_feature_updated_on BEFORE UPDATE ON designdb.features FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_route_updated_on ON designdb.routes;
CREATE TRIGGER trg_route_updated_on BEFORE UPDATE ON designdb.routes FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_reaction_updated_on ON designdb.reactions;
CREATE TRIGGER trg_reaction_updated_on BEFORE UPDATE ON designdb.reactions FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_pose_updated_on ON designdb.poses;
CREATE TRIGGER trg_pose_updated_on BEFORE UPDATE ON designdb.poses FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_scores_updated_on ON designdb.scores;
CREATE TRIGGER trg_scores_updated_on BEFORE UPDATE ON designdb.scores FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_scores_refresh_pivoted_mv ON designdb.scores;
CREATE TRIGGER trg_scores_refresh_pivoted_mv
  AFTER INSERT OR UPDATE OR DELETE ON designdb.scores
  FOR EACH STATEMENT EXECUTE FUNCTION designdb.refresh_scores_per_pose_pivoted_mv();

DROP TRIGGER IF EXISTS trg_subsite_updated_on ON designdb.subsites;
CREATE TRIGGER trg_subsite_updated_on BEFORE UPDATE ON designdb.subsites FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_component_updated_on ON designdb.components;
CREATE TRIGGER trg_component_updated_on BEFORE UPDATE ON designdb.components FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_inspiration_updated_on ON designdb.inspirations;
CREATE TRIGGER trg_inspiration_updated_on BEFORE UPDATE ON designdb.inspirations FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_interaction_updated_on ON designdb.interactions;
CREATE TRIGGER trg_interaction_updated_on BEFORE UPDATE ON designdb.interactions FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_quote_updated_on ON designdb.quotes;
CREATE TRIGGER trg_quote_updated_on BEFORE UPDATE ON designdb.quotes FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

-- =========================================================
-- AUDIT TRIGGERS
-- =========================================================

DROP TRIGGER IF EXISTS trg_quotes_event_audit ON designdb.quotes;
CREATE TRIGGER trg_quotes_event_audit
    AFTER INSERT OR UPDATE OR DELETE ON designdb.quotes
    FOR EACH ROW
    EXECUTE FUNCTION designdb.event_audit_trigger(
        'designdb.quotes_event_audit',
        'id',
        'created_on,updated_on',
        ''
    );

DROP TRIGGER IF EXISTS trg_pose_tags_event_audit ON designdb.pose_tags;
CREATE TRIGGER trg_pose_tags_event_audit
    AFTER INSERT OR UPDATE OR DELETE ON designdb.pose_tags
    FOR EACH ROW
    EXECUTE FUNCTION designdb.event_audit_trigger(
        'designdb.pose_tags_event_audit',
        'id',
        'created_on,updated_on',
        ''
    );

DROP TRIGGER IF EXISTS trg_compound_tags_event_audit ON designdb.compound_tags;
CREATE TRIGGER trg_compound_tags_event_audit
    AFTER INSERT OR UPDATE OR DELETE ON designdb.compound_tags
    FOR EACH ROW
    EXECUTE FUNCTION designdb.event_audit_trigger(
        'designdb.compound_tags_event_audit',
        'id',
        'created_on,updated_on',
        ''
    );

DROP TRIGGER IF EXISTS trg_pose_methods_event_audit ON designdb.pose_methods;
CREATE TRIGGER trg_pose_methods_event_audit
    AFTER INSERT OR UPDATE OR DELETE ON designdb.pose_methods
    FOR EACH ROW
    EXECUTE FUNCTION designdb.event_audit_trigger(
        'designdb.pose_methods_event_audit',
        'id',
        'created_on,updated_on',
        ''
    );

DROP TRIGGER IF EXISTS trg_enumeration_methods_event_audit ON designdb.enumeration_methods;
CREATE TRIGGER trg_enumeration_methods_event_audit
    AFTER INSERT OR UPDATE OR DELETE ON designdb.enumeration_methods
    FOR EACH ROW
    EXECUTE FUNCTION designdb.event_audit_trigger(
        'designdb.enumeration_methods_event_audit',
        'id',
        'created_on,updated_on',
        ''
    );

DROP TRIGGER IF EXISTS trg_scoring_methods_event_audit ON designdb.scoring_methods;
CREATE TRIGGER trg_scoring_methods_event_audit
    AFTER INSERT OR UPDATE OR DELETE ON designdb.scoring_methods
    FOR EACH ROW
    EXECUTE FUNCTION designdb.event_audit_trigger(
        'designdb.scoring_methods_event_audit',
        'id',
        'created_on,updated_on',
        ''
    );

DROP TRIGGER IF EXISTS trg_reactant_updated_on ON designdb.reactants;
CREATE TRIGGER trg_reactant_updated_on BEFORE UPDATE ON designdb.reactants FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_scaffold_updated_on ON designdb.scaffolds;
CREATE TRIGGER trg_scaffold_updated_on BEFORE UPDATE ON designdb.scaffolds FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_subsite_tag_updated_on ON designdb.subsite_tags;
CREATE TRIGGER trg_subsite_tag_updated_on BEFORE UPDATE ON designdb.subsite_tags FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

-- Removed due to replaced tables
-- DROP TRIGGER IF EXISTS trg_tag_updated_on ON designdb.tags;
-- CREATE TRIGGER trg_tag_updated_on BEFORE UPDATE ON designdb.tags FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_pose_tag_updated_on ON designdb.pose_tags;
CREATE TRIGGER trg_pose_tag_updated_on BEFORE UPDATE ON designdb.pose_tags FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_compound_tag_updated_on ON designdb.compound_tags;
CREATE TRIGGER trg_compound_tag_updated_on BEFORE UPDATE ON designdb.compound_tags FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_has_pose_tag_updated_on ON designdb.has_pose_tags;
CREATE TRIGGER trg_has_pose_tag_updated_on BEFORE UPDATE ON designdb.has_pose_tags FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_has_pose_methods_updated_on ON designdb.has_pose_methods;
CREATE TRIGGER trg_has_pose_methods_updated_on BEFORE UPDATE ON designdb.has_pose_methods FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_has_compound_tag_updated_on ON designdb.has_compound_tags;
CREATE TRIGGER trg_has_compound_tag_updated_on BEFORE UPDATE ON designdb.has_compound_tags FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_has_enumeration_methods_updated_on ON designdb.has_enumeration_methods;
CREATE TRIGGER trg_has_enumeration_methods_updated_on BEFORE UPDATE ON designdb.has_enumeration_methods FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

-- Pivoted materialized view once at schema load, this will be mapped in Scarab to do the filtering based on any type of scores/methods
SELECT designdb.create_scores_per_pose_pivoted_mv();
