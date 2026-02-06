#!/usr/bin/env node

/**
 * Initial Sync: Import existing .beads/issues.jsonl to Supabase
 * Run once to populate bd_issues table with existing issues
 * 
 * Usage:
 *   node scripts/sync-beads-to-supabase.js
 * 
 * Requirements:
 *   - SUPABASE_URL in .env
 *   - SUPABASE_SERVICE_ROLE_KEY in .env
 *   - .beads/issues.jsonl exists
 */

const fs = require('fs');
const path = require('path');
const { createClient } = require('@supabase/supabase-js');
require('dotenv').config();

const BEADS_FILE = path.join(__dirname, '../.beads/issues.jsonl');
const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

// Validate environment
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('❌ Missing environment variables!');
  console.error('Required: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY');
  console.error('Create .env file with these variables');
  process.exit(1);
}

if (!fs.existsSync(BEADS_FILE)) {
  console.error(`❌ File not found: ${BEADS_FILE}`);
  process.exit(1);
}

// Initialize Supabase client
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

/**
 * Parse JSONL file
 */
function parseJSONL(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  return content
    .split('\n')
    .filter(line => line.trim())
    .map(line => JSON.parse(line));
}

/**
 * Get project ID for Ne4nf/Spec
 */
async function getProjectId() {
  const { data, error } = await supabase
    .from('projects')
    .select('id')
    .eq('repo_owner', 'Ne4nf')
    .eq('repo_name', 'Spec')
    .single();
  
  if (error) {
    throw new Error(`Failed to find project: ${error.message}`);
  }
  
  if (!data) {
    throw new Error('Project Ne4nf/Spec not found in database. Run schema migration first.');
  }
  
  return data.id;
}

/**
 * Sync single issue
 */
async function syncIssue(projectId, issue) {
  const { error } = await supabase.rpc('upsert_bd_issue', {
    p_project_id: projectId,
    p_id: issue.id,
    p_title: issue.title,
    p_description: issue.description || null,
    p_status: issue.status,
    p_priority: issue.priority,
    p_issue_type: issue.issue_type,
    p_design: issue.design || null,
    p_acceptance_criteria: issue.acceptance_criteria || null,
    p_labels: issue.labels || [],
    p_created_at: issue.created_at,
    p_updated_at: issue.updated_at
  });

  if (error) {
    throw new Error(`Failed to sync issue ${issue.id}: ${error.message}`);
  }

  return issue.id;
}

/**
 * Sync dependencies
 */
async function syncDependencies(projectId, issue) {
  if (!issue.dependencies || issue.dependencies.length === 0) {
    return 0;
  }

  let count = 0;
  for (const dep of issue.dependencies) {
    const { error } = await supabase
      .from('bd_dependencies')
      .upsert({
        project_id: projectId,
        issue_id: dep.issue_id,
        depends_on_id: dep.depends_on_id,
        dependency_type: dep.type,
        created_at: dep.created_at,
        created_by: dep.created_by
      }, {
        onConflict: 'project_id,issue_id,depends_on_id,dependency_type'
      });

    if (error) {
      console.warn(`⚠️  Failed to sync dependency ${dep.issue_id} → ${dep.depends_on_id}: ${error.message}`);
    } else {
      count++;
    }
  }

  return count;
}

/**
 * Sync comments
 */
async function syncComments(projectId, issue) {
  if (!issue.comments || issue.comments.length === 0) {
    return 0;
  }

  let count = 0;
  for (const comment of issue.comments) {
    const { error } = await supabase
      .from('bd_comments')
      .insert({
        project_id: projectId,
        issue_id: comment.issue_id,
        author: comment.author,
        text: comment.text,
        created_at: comment.created_at
      });

    if (error && error.code !== '23505') { // Ignore duplicates
      console.warn(`⚠️  Failed to sync comment on ${issue.id}: ${error.message}`);
    } else if (!error) {
      count++;
    }
  }

  return count;
}

/**
 * Main sync process
 */
async function main() {
  console.log('🔄 Starting beads → Supabase sync...\n');

  try {
    // 1. Load issues
    console.log('📖 Reading .beads/issues.jsonl...');
    const issues = parseJSONL(BEADS_FILE);
    console.log(`   Found ${issues.length} issues\n`);

    // 2. Get project ID
    console.log('🔍 Looking up project...');
    const projectId = await getProjectId();
    console.log(`   Project ID: ${projectId}\n`);

    // 3. Sync issues
    console.log('📝 Syncing issues...');
    let issueCount = 0;
    let depCount = 0;
    let commentCount = 0;

    for (const issue of issues) {
      try {
        await syncIssue(projectId, issue);
        issueCount++;
        
        const deps = await syncDependencies(projectId, issue);
        depCount += deps;
        
        const comments = await syncComments(projectId, issue);
        commentCount += comments;
        
        console.log(`   ✓ ${issue.id}: ${issue.title}`);
      } catch (error) {
        console.error(`   ✗ ${issue.id}: ${error.message}`);
      }
    }

    console.log('\n✅ Sync completed!');
    console.log(`   Issues: ${issueCount}/${issues.length}`);
    console.log(`   Dependencies: ${depCount}`);
    console.log(`   Comments: ${commentCount}`);

    // 4. Verify
    console.log('\n🔍 Verifying...');
    const { count, error } = await supabase
      .from('bd_issues')
      .select('*', { count: 'exact', head: true })
      .eq('project_id', projectId);

    if (error) {
      console.error(`⚠️  Verification failed: ${error.message}`);
    } else {
      console.log(`   Database has ${count} issues for this project`);
    }

    console.log('\n🎉 Done! Check Supabase dashboard to see your issues.');
    console.log(`   URL: ${SUPABASE_URL}/project/_/editor`);

  } catch (error) {
    console.error('\n❌ Sync failed:', error.message);
    process.exit(1);
  }
}

// Run
main();
