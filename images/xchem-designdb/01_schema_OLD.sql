-- =========================================================
-- designdb Database Schema
-- =========================================================

-- =========================================================
-- PREREQUISITES & EXTENSIONS
-- =========================================================

DROP SCHEMA IF EXISTS designdb CASCADE;
CREATE SCHEMA IF NOT EXISTS designdb;
CREATE SCHEMA IF NOT EXISTS rdkit;

CREATE EXTENSION IF NOT EXISTS rdkit WITH SCHEMA rdkit;
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA designdb;

SET search_path TO designdb, rdkit, public;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- =========================================================
-- TABLES (ordered by FK dependencies)
-- =========================================================

CREATE TABLE IF NOT EXISTS designdb.target (
    target_pk BIGSERIAL PRIMARY KEY, --Must be a link to Scarab protein production target
    target_name TEXT, --Insert from HIPPO codebase. Must be a link to Scarab protein production target
    target_metadata TEXT, -- Not populated by code
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_target UNIQUE (target_name)
);

-- New table
CREATE TABLE IF NOT EXISTS designdb.scoring_method (
    method_pk BIGSERIAL PRIMARY KEY,
    method_name TEXT,
    method_description TEXT,
    method_version TEXT,
    method_organization TEXT,
    method_link TEXT,
    note TEXT,
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS designdb.enumeration_method (
    enum_pk BIGSERIAL PRIMARY KEY,
    enum_name TEXT,
    enum_description TEXT,
    enum_version TEXT,
    enum_organization TEXT,
    enum_link TEXT,
    enum_note TEXT,
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS designdb.pose_method (
    pose_method_pk BIGSERIAL PRIMARY KEY,
    pose_method_name TEXT,
    pose_method_description TEXT,
    pose_method_version TEXT,
    pose_method_organization TEXT,
    pose_method_link TEXT,
    pose_method_note TEXT,
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS designdb.compound (
    compound_pk BIGSERIAL PRIMARY KEY,
    compound_inchikey TEXT, -- Maybe insert by the codebase or jupyter. Do we need to write this by code or can be calculated by the cartridge?
    compound_alias TEXT, -- Maybe insert by the codebase.
    compound_smiles TEXT, -- Inseret by the codebase. Is this 2d flat smiles without any stereochemistry? LR - Yes 2D. Looks like designdb function sanitise_smiles does remove stereochemistry - will this be a problem when a user wants to register a design with defined stereochemistry?
    compound_base BIGINT REFERENCES designdb.compound (compound_pk) ON DELETE SET NULL, -- Not populated by code
    compound_mol rdkit.mol, -- Maybe insert from codebase and/or Chemicalite/Postgres RDKit cartridge
    compound_pattern_bfp bit(2048), -- Postgres RDkit cartridge can calc this, Chemicalite does, not sure if insert by codebase. Currently its broken
    compound_morgan_bfp bit(2048), -- Postgresartridge can't calc this. Msut be insert by codebase, but currently its broken
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

CREATE TABLE IF NOT EXISTS designdb.feature (
    feature_pk BIGSERIAL PRIMARY KEY,
    feature_family TEXT, -- Insert by codebase
    feature_target BIGINT REFERENCES designdb.target (target_pk) ON DELETE RESTRICT, -- Insert by codebase
    feature_chain_name TEXT, -- Insert by codebase
    feature_residue_name TEXT, -- Insert by codebase
    feature_residue_number INTEGER, -- Insert by codebase
    feature_atom_names TEXT, -- Insert by codebase
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_feature UNIQUE (feature_family, feature_target, feature_chain_name, feature_residue_number, feature_residue_name, feature_atom_names)
);

CREATE TABLE IF NOT EXISTS designdb.route (
    route_pk BIGSERIAL PRIMARY KEY,
    route_product BIGINT REFERENCES designdb.compound (compound_pk) ON DELETE RESTRICT, -- Insert by codebase/notebook, Synderilla
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS designdb.reaction (
    reaction_pk BIGSERIAL PRIMARY KEY,
    reaction_type TEXT, -- Insert by codebase/notebook, Synderilla
    reaction_product BIGINT REFERENCES designdb.compound (compound_pk) ON DELETE RESTRICT, -- Insert by codebase/notebook, Synderilla
    reaction_product_yield REAL, -- Insert by codebase/notebook, Synderilla
    reaction_metadata TEXT, -- Not populated by code
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS designdb.pose (
    pose_pk BIGSERIAL PRIMARY KEY,
    pose_inchikey TEXT, -- Insert by codebase when registering poses? Might be done from pose.mol?
    pose_alias TEXT,
    pose_smiles TEXT, -- LR - necessary because will contain defined stereochemistry - should these be canonicalised? Is it done by codebase from pose.mol? Could be done by RDkit cartridge.
    pose_reference INTEGER,
    pose_path TEXT,
    pose_compound BIGINT REFERENCES designdb.compound (compound_pk) ON DELETE RESTRICT,
    pose_target BIGINT REFERENCES designdb.target (target_pk) ON DELETE RESTRICT,
    pose_mol rdkit.mol, -- Insert by the codebase and /or Chemicalite/Postgres RDkit cartridge
    pose_fingerprint INTEGER,
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

CREATE TABLE IF NOT EXISTS designdb.scores (
    score_pk BIGSERIAL PRIMARY KEY,
    pose_pk BIGINT NOT NULL REFERENCES designdb.pose (pose_pk) ON DELETE RESTRICT,
    compound_pk BIGINT REFERENCES designdb.compound (compound_pk) ON DELETE SET NULL,
    score JSONB,  -- method_name -> {"score": number, "version": text}
    note TEXT,
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS designdb.subsite (
    subsite_pk BIGSERIAL PRIMARY KEY,
    subsite_target BIGINT NOT NULL REFERENCES designdb.target (target_pk) ON DELETE RESTRICT, -- Insert by codebase/notebook
    subsite_name TEXT NOT NULL, -- Insert by codebase/notebook
    subsite_metadata TEXT, -- Not populated by code
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_subsite UNIQUE (subsite_target, subsite_name)
);

CREATE TABLE IF NOT EXISTS designdb.component (
    component_pk BIGSERIAL PRIMARY KEY,
    component_route BIGINT REFERENCES designdb.route (route_pk) ON DELETE RESTRICT, -- Insert by codebase/notebook, Synderilla
    component_type INTEGER, -- Insert by codebase/notebook, Synderilla--
    component_ref INTEGER, -- Insert by codebase/notebook, Synderilla
    component_amount REAL, -- Insert by codebase/notebook, Synderilla
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_component UNIQUE (component_route, component_ref, component_type)
);

CREATE TABLE IF NOT EXISTS designdb.inspiration (
    inspiration_pk BIGSERIAL PRIMARY KEY,
    inspiration_original BIGINT REFERENCES designdb.pose (pose_pk) ON DELETE SET NULL, -- Insert by codebase
    inspiration_derivative BIGINT REFERENCES designdb.pose (pose_pk) ON DELETE SET NULL, -- Insert by codebase
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_inspiration UNIQUE (inspiration_original, inspiration_derivative)
);

CREATE TABLE IF NOT EXISTS designdb.interaction (
    interaction_pk BIGSERIAL PRIMARY KEY,
    interaction_feature BIGINT NOT NULL REFERENCES designdb.feature (feature_pk) ON DELETE RESTRICT, -- Insert by codebase
    interaction_pose BIGINT NOT NULL REFERENCES designdb.pose (pose_pk) ON DELETE RESTRICT, -- Insert by codebase
    interaction_type TEXT NOT NULL, -- Insert by codebase
    interaction_family TEXT NOT NULL, -- Insert by codebase
    interaction_atom_ids TEXT NOT NULL, -- Insert by codebase
    interaction_prot_coord TEXT NOT NULL, -- Insert by codebase. Not populated by ProLIF, needs reviewing
    interaction_lig_coord TEXT NOT NULL, -- Insert by codebase. Not populated by ProLIF, needs reviewing
    interaction_distance REAL NOT NULL, -- Insert by codebase
    interaction_angle REAL, -- Insert by codebase
    interaction_energy REAL, -- Insert by codebase. Not populated by ProLIF, needs reviewing
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_interaction UNIQUE (interaction_feature, interaction_pose, interaction_type, interaction_family, interaction_atom_ids)
);

CREATE TABLE IF NOT EXISTS designdb.quote (
    quote_pk BIGSERIAL PRIMARY KEY,
    quote_smiles TEXT, -- From compound
    quote_mol rdkit.mol, -- New column, should be generated by cartridge
    quote_amount REAL,
    quote_supplier TEXT,
    quote_catalogue TEXT,
    quote_entry TEXT,
    quote_lead_time INTEGER,
    quote_price REAL,
    quote_currency TEXT,
    quote_purity REAL,
    quote_date TEXT,
    quote_compound BIGINT REFERENCES designdb.compound (compound_pk) ON DELETE SET NULL,
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_quote UNIQUE (quote_amount, quote_supplier, quote_catalogue, quote_entry)
);

CREATE TABLE IF NOT EXISTS designdb.reactant (
    reactant_pk BIGSERIAL PRIMARY KEY,
    reactant_amount REAL, -- Insert by codebase/notebook, Synderilla
    reactant_reaction BIGINT REFERENCES designdb.reaction (reaction_pk) ON DELETE CASCADE, -- Insert by codebase/notebook, Synderilla
    reactant_compound BIGINT REFERENCES designdb.compound (compound_pk) ON DELETE RESTRICT, -- Insert by codebase/notebook, Synderilla
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_reactant UNIQUE (reactant_reaction, reactant_compound)
);

CREATE TABLE IF NOT EXISTS designdb.scaffold (
    scaffold_pk BIGSERIAL PRIMARY KEY,
    scaffold_base BIGINT REFERENCES designdb.compound (compound_pk) ON DELETE SET NULL, -- Insert by codebase
    scaffold_superstructure BIGINT REFERENCES designdb.compound (compound_pk) ON DELETE SET NULL, -- Insert by codebase
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_scaffold UNIQUE (scaffold_base, scaffold_superstructure)
);

CREATE TABLE IF NOT EXISTS designdb.subsite_tag (
    subsite_tag_pk BIGSERIAL PRIMARY KEY,
    subsite_tag_ref BIGINT NOT NULL REFERENCES designdb.subsite (subsite_pk) ON DELETE RESTRICT, -- Insert by codebase
    subsite_tag_pose BIGINT NOT NULL REFERENCES designdb.pose (pose_pk) ON DELETE RESTRICT, -- Insert by codebase
    subsite_tag_metadata TEXT, -- Not populated by code
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_subsite_tag UNIQUE (subsite_tag_ref, subsite_tag_pose)
);

-- CREATE TABLE IF NOT EXISTS designdb.tag (
--     tag_pk BIGSERIAL PRIMARY KEY,
--     tag_name TEXT, -- Insert by codebase
--     tag_description TEXT, -- New column
--     note TEXT, -- New column
--     -- tag_compound BIGINT REFERENCES designdb.compound (compound_pk) ON DELETE SET NULL, -- Insert by codebase, need to be removed, change in code needed
--     -- tag_pose BIGINT REFERENCES designdb.pose (pose_pk) ON DELETE SET NULL, -- Insert by codebase, need to be removed, change in code needed
--     created_on TIMESTAMPTZ DEFAULT now(),
--     updated_on TIMESTAMPTZ DEFAULT now()
--     -- CONSTRAINT uc_tag_compound UNIQUE (tag_name, tag_compound),
--     -- CONSTRAINT uc_tag_pose UNIQUE (tag_name, tag_pose)
-- );

CREATE TABLE IF NOT EXISTS designdb.pose_tag (
    pose_tag_pk BIGSERIAL PRIMARY KEY,
    pose_tag_name TEXT,
    pose_tag_description TEXT,
    pose_tag_note TEXT,
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS designdb.compound_tag (
    compound_tag_pk BIGSERIAL PRIMARY KEY,
    compound_tag_name TEXT,
    compound_tag_description TEXT,
    compound_tag_note TEXT,
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now()
);

-- =========================================================
-- New tables supporting tagging

CREATE TABLE IF NOT EXISTS designdb.has_pose_tag (
    has_pose_tag_pk BIGSERIAL PRIMARY KEY,
    pose_pk BIGINT NOT NULL REFERENCES designdb.pose (pose_pk) ON DELETE CASCADE,
    pose_tag_pk BIGINT NOT NULL REFERENCES designdb.pose_tag (pose_tag_pk) ON DELETE CASCADE,
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_has_pose_tag UNIQUE (pose_pk, pose_tag_pk)
);

CREATE TABLE IF NOT EXISTS designdb.has_compound_tag (
    has_compound_tag_pk BIGSERIAL PRIMARY KEY,
    compound_pk BIGINT NOT NULL REFERENCES designdb.compound (compound_pk) ON DELETE CASCADE,
    compound_tag_pk BIGINT NOT NULL REFERENCES designdb.compound_tag (compound_tag_pk) ON DELETE CASCADE,
    created_on TIMESTAMPTZ DEFAULT now(),
    updated_on TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uc_has_compound_tag UNIQUE (compound_pk, compound_tag_pk)
);

-- =========================================================
-- INDEXES
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_target_name ON designdb.target(target_name);
CREATE INDEX IF NOT EXISTS idx_target_created ON designdb.target(created_on);

CREATE INDEX IF NOT EXISTS idx_scoring_method_name ON designdb.scoring_method(method_name);
CREATE INDEX IF NOT EXISTS idx_scoring_method_created ON designdb.scoring_method(created_on);

CREATE INDEX IF NOT EXISTS idx_enumeration_method_name ON designdb.enumeration_method(enum_name);
CREATE INDEX IF NOT EXISTS idx_enumeration_method_created ON designdb.enumeration_method(created_on);

CREATE INDEX IF NOT EXISTS idx_pose_method_name ON designdb.pose_method(pose_method_name);
CREATE INDEX IF NOT EXISTS idx_pose_method_created ON designdb.pose_method(created_on);

CREATE INDEX IF NOT EXISTS idx_compound_base ON designdb.compound(compound_base);
CREATE INDEX IF NOT EXISTS idx_compound_inchikey ON designdb.compound(compound_inchikey);
CREATE INDEX IF NOT EXISTS idx_compound_smiles ON designdb.compound(compound_smiles);
CREATE INDEX IF NOT EXISTS idx_compound_created ON designdb.compound(created_on);

CREATE INDEX IF NOT EXISTS idx_feature_target ON designdb.feature(feature_target);
CREATE INDEX IF NOT EXISTS idx_feature_created ON designdb.feature(created_on);

CREATE INDEX IF NOT EXISTS idx_route_product ON designdb.route(route_product);
CREATE INDEX IF NOT EXISTS idx_route_created ON designdb.route(created_on);

CREATE INDEX IF NOT EXISTS idx_reaction_product ON designdb.reaction(reaction_product);
CREATE INDEX IF NOT EXISTS idx_reaction_created ON designdb.reaction(created_on);

CREATE INDEX IF NOT EXISTS idx_pose_compound ON designdb.pose(pose_compound);
CREATE INDEX IF NOT EXISTS idx_pose_target ON designdb.pose(pose_target);
CREATE INDEX IF NOT EXISTS idx_pose_path ON designdb.pose(pose_path);
CREATE INDEX IF NOT EXISTS idx_pose_created ON designdb.pose(created_on);

CREATE INDEX IF NOT EXISTS idx_scores_pose_pk ON designdb.scores(pose_pk);
CREATE INDEX IF NOT EXISTS idx_scores_compound_pk ON designdb.scores(compound_pk);
CREATE INDEX IF NOT EXISTS idx_scores_created ON designdb.scores(created_on);
CREATE INDEX IF NOT EXISTS idx_scores_score_gin ON designdb.scores USING GIN (score);

CREATE INDEX IF NOT EXISTS idx_subsite_target ON designdb.subsite(subsite_target);
CREATE INDEX IF NOT EXISTS idx_subsite_created ON designdb.subsite(created_on);

CREATE INDEX IF NOT EXISTS idx_component_route ON designdb.component(component_route);
CREATE INDEX IF NOT EXISTS idx_component_created ON designdb.component(created_on);

CREATE INDEX IF NOT EXISTS idx_inspiration_original ON designdb.inspiration(inspiration_original);
CREATE INDEX IF NOT EXISTS idx_inspiration_derivative ON designdb.inspiration(inspiration_derivative);
CREATE INDEX IF NOT EXISTS idx_inspiration_created ON designdb.inspiration(created_on);

CREATE INDEX IF NOT EXISTS idx_interaction_feature ON designdb.interaction(interaction_feature);
CREATE INDEX IF NOT EXISTS idx_interaction_pose ON designdb.interaction(interaction_pose);
CREATE INDEX IF NOT EXISTS idx_interaction_created ON designdb.interaction(created_on);

CREATE INDEX IF NOT EXISTS idx_quote_compound ON designdb.quote(quote_compound);
CREATE INDEX IF NOT EXISTS idx_quote_created ON designdb.quote(created_on);

CREATE INDEX IF NOT EXISTS idx_reactant_reaction ON designdb.reactant(reactant_reaction);
CREATE INDEX IF NOT EXISTS idx_reactant_compound ON designdb.reactant(reactant_compound);
CREATE INDEX IF NOT EXISTS idx_reactant_created ON designdb.reactant(created_on);

CREATE INDEX IF NOT EXISTS idx_scaffold_base ON designdb.scaffold(scaffold_base);
CREATE INDEX IF NOT EXISTS idx_scaffold_superstructure ON designdb.scaffold(scaffold_superstructure);
CREATE INDEX IF NOT EXISTS idx_scaffold_created ON designdb.scaffold(created_on);

CREATE INDEX IF NOT EXISTS idx_subsite_tag_ref ON designdb.subsite_tag(subsite_tag_ref);
CREATE INDEX IF NOT EXISTS idx_subsite_tag_pose ON designdb.subsite_tag(subsite_tag_pose);
CREATE INDEX IF NOT EXISTS idx_subsite_tag_created ON designdb.subsite_tag(created_on);

-- CREATE INDEX IF NOT EXISTS idx_tag_compound ON designdb.tag(tag_compound);
-- CREATE INDEX IF NOT EXISTS idx_tag_pose ON designdb.tag(tag_pose);
-- CREATE INDEX IF NOT EXISTS idx_tag_created ON designdb.tag(created_on);

CREATE INDEX IF NOT EXISTS idx_pose_tag_created ON designdb.pose_tag(created_on);
CREATE INDEX IF NOT EXISTS idx_compound_tag_created ON designdb.compound_tag(created_on);

CREATE INDEX IF NOT EXISTS idx_has_pose_tag_pose_pk ON designdb.has_pose_tag(pose_pk);
CREATE INDEX IF NOT EXISTS idx_has_pose_tag_pose_tag_pk ON designdb.has_pose_tag(pose_tag_pk);
CREATE INDEX IF NOT EXISTS idx_has_pose_tag_created ON designdb.has_pose_tag(created_on);

CREATE INDEX IF NOT EXISTS idx_has_compound_tag_compound_pk ON designdb.has_compound_tag(compound_pk);
CREATE INDEX IF NOT EXISTS idx_has_compound_tag_compound_tag_pk ON designdb.has_compound_tag(compound_tag_pk);
CREATE INDEX IF NOT EXISTS idx_has_compound_tag_created ON designdb.has_compound_tag(created_on);

-- =========================================================
-- FUNCTIONS
-- =========================================================

CREATE OR REPLACE FUNCTION designdb.update_updated_on()
RETURNS trigger AS $$
BEGIN
    NEW.updated_on = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =========================================================
-- TRIGGERS (updated_on)
-- =========================================================

DROP TRIGGER IF EXISTS trg_target_updated_on ON designdb.target;
CREATE TRIGGER trg_target_updated_on BEFORE UPDATE ON designdb.target FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_scoring_method_updated_on ON designdb.scoring_method;
CREATE TRIGGER trg_scoring_method_updated_on BEFORE UPDATE ON designdb.scoring_method FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_enumeration_method_updated_on ON designdb.enumeration_method;
CREATE TRIGGER trg_enumeration_method_updated_on BEFORE UPDATE ON designdb.enumeration_method FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_pose_method_updated_on ON designdb.pose_method;
CREATE TRIGGER trg_pose_method_updated_on BEFORE UPDATE ON designdb.pose_method FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_compound_updated_on ON designdb.compound;
CREATE TRIGGER trg_compound_updated_on BEFORE UPDATE ON designdb.compound FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_feature_updated_on ON designdb.feature;
CREATE TRIGGER trg_feature_updated_on BEFORE UPDATE ON designdb.feature FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_route_updated_on ON designdb.route;
CREATE TRIGGER trg_route_updated_on BEFORE UPDATE ON designdb.route FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_reaction_updated_on ON designdb.reaction;
CREATE TRIGGER trg_reaction_updated_on BEFORE UPDATE ON designdb.reaction FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_pose_updated_on ON designdb.pose;
CREATE TRIGGER trg_pose_updated_on BEFORE UPDATE ON designdb.pose FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_scores_updated_on ON designdb.scores;
CREATE TRIGGER trg_scores_updated_on BEFORE UPDATE ON designdb.scores FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_subsite_updated_on ON designdb.subsite;
CREATE TRIGGER trg_subsite_updated_on BEFORE UPDATE ON designdb.subsite FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_component_updated_on ON designdb.component;
CREATE TRIGGER trg_component_updated_on BEFORE UPDATE ON designdb.component FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_inspiration_updated_on ON designdb.inspiration;
CREATE TRIGGER trg_inspiration_updated_on BEFORE UPDATE ON designdb.inspiration FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_interaction_updated_on ON designdb.interaction;
CREATE TRIGGER trg_interaction_updated_on BEFORE UPDATE ON designdb.interaction FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_quote_updated_on ON designdb.quote;
CREATE TRIGGER trg_quote_updated_on BEFORE UPDATE ON designdb.quote FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_reactant_updated_on ON designdb.reactant;
CREATE TRIGGER trg_reactant_updated_on BEFORE UPDATE ON designdb.reactant FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_scaffold_updated_on ON designdb.scaffold;
CREATE TRIGGER trg_scaffold_updated_on BEFORE UPDATE ON designdb.scaffold FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_subsite_tag_updated_on ON designdb.subsite_tag;
CREATE TRIGGER trg_subsite_tag_updated_on BEFORE UPDATE ON designdb.subsite_tag FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

-- DROP TRIGGER IF EXISTS trg_tag_updated_on ON designdb.tag;
-- CREATE TRIGGER trg_tag_updated_on BEFORE UPDATE ON designdb.tag FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_pose_tag_updated_on ON designdb.pose_tag;
CREATE TRIGGER trg_pose_tag_updated_on BEFORE UPDATE ON designdb.pose_tag FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_compound_tag_updated_on ON designdb.compound_tag;
CREATE TRIGGER trg_compound_tag_updated_on BEFORE UPDATE ON designdb.compound_tag FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_has_pose_tag_updated_on ON designdb.has_pose_tag;
CREATE TRIGGER trg_has_pose_tag_updated_on BEFORE UPDATE ON designdb.has_pose_tag FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();

DROP TRIGGER IF EXISTS trg_has_compound_tag_updated_on ON designdb.has_compound_tag;
CREATE TRIGGER trg_has_compound_tag_updated_on BEFORE UPDATE ON designdb.has_compound_tag FOR EACH ROW EXECUTE FUNCTION designdb.update_updated_on();
