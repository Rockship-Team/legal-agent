const { createClient } = require('@supabase/supabase-js');
require('dotenv').config();

// Read credentials from environment variables
const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl || !supabaseKey) {
  console.error('❌ Error: SUPABASE_URL and SUPABASE_KEY environment variables are required');
  console.error('   Set these in .env file or shell environment.');
  console.error('   See README.md for configuration instructions.');
  process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseKey);

async function getReviewComments(specPath) {
  console.log('🔍 Searching for review comments...');
  console.log('   Spec path pattern:', specPath);

  // Get all review_comments matching the spec path
  const { data: comments, error } = await supabase
    .from('review_comments')
    .select(`
      *,
      changes!inner(
        id,
        head_branch,
        base_branch,
        state,
        spec_id,
        specs!inner(
          spec_key,
          project_id,
          projects!inner(
            repo_owner,
            repo_name
          )
        )
      )
    `)
    .like('file_path', specPath + '%')
    .eq('is_resolved', false);

  if (error) {
    console.error('Error querying review_comments:', error.message);

    // Try simpler query
    const { data: simpleComments, error: simpleError } = await supabase
      .from('review_comments')
      .select('*')
      .like('file_path', specPath + '%')
      .eq('is_resolved', false);

    if (simpleError) {
      console.error('Simple query also failed:', simpleError.message);
      return null;
    }

    console.log('\n📬 Found', simpleComments?.length || 0, 'unresolved review comments');
    return simpleComments;
  }

  console.log('\n📬 Found', comments?.length || 0, 'unresolved review comments');
  return comments;
}

async function getReviewCommentsByChangeId(changeId) {
  const { data, error } = await supabase
    .from('review_comments')
    .select('*')
    .eq('change_id', changeId)
    .eq('is_resolved', false)
    .order('file_path')
    .order('start_line');

  if (error) {
    console.error('Error:', error.message);
    return null;
  }

  return data;
}

async function getChangesForProject(repoOwner, repoName) {
  // First get project
  const { data: project } = await supabase
    .from('projects')
    .select('id')
    .eq('repo_owner', repoOwner)
    .eq('repo_name', repoName)
    .single();

  if (!project) {
    console.error('Project not found:', repoOwner + '/' + repoName);
    return null;
  }

  // Get specs for project
  const { data: specs } = await supabase
    .from('specs')
    .select('id, spec_key')
    .eq('project_id', project.id);

  if (!specs || specs.length === 0) {
    console.log('No specs found for project');
    return null;
  }

  // Get changes for specs
  const specIds = specs.map(s => s.id);
  const { data: changes } = await supabase
    .from('changes')
    .select('*')
    .in('spec_id', specIds)
    .eq('state', 'open');

  return { project, specs, changes };
}

async function getAllReviewCommentsForProject(repoOwner, repoName) {
  const projectData = await getChangesForProject(repoOwner, repoName);

  if (!projectData || !projectData.changes) {
    console.log('No open changes found');
    return [];
  }

  const allComments = [];

  for (const change of projectData.changes) {
    const comments = await getReviewCommentsByChangeId(change.id);
    if (comments && comments.length > 0) {
      allComments.push({
        change,
        comments
      });
    }
  }

  return allComments;
}

async function resolveComment(commentId) {
  const { error } = await supabase
    .from('review_comments')
    .update({ is_resolved: true })
    .eq('id', commentId);

  if (error) {
    console.error('Error resolving comment:', error.message);
    return { success: false, error: error.message };
  }

  return { success: true, id: commentId };
}

async function resolveComments(commentIds) {
  const results = [];
  for (const id of commentIds) {
    const result = await resolveComment(id);
    results.push(result);
  }
  return results;
}

// CLI
const args = process.argv.slice(2);
const command = args[0];

if (command === 'by-path') {
  const specPath = args[1] || 'specs/001-connect-superbase';
  getReviewComments(specPath).then(comments => {
    console.log(JSON.stringify(comments, null, 2));
  });
} else if (command === 'by-project') {
  const repoOwner = args[1] || 'Rockship-Team';
  const repoName = args[2] || 'upwork-crawl-job';
  getAllReviewCommentsForProject(repoOwner, repoName).then(result => {
    console.log(JSON.stringify(result, null, 2));
  });
} else if (command === 'by-change') {
  const changeId = args[1];
  if (!changeId) {
    console.error('Usage: node get-review-comments.js by-change <change-id>');
    process.exit(1);
  }
  getReviewCommentsByChangeId(changeId).then(comments => {
    console.log(JSON.stringify(comments, null, 2));
  });
} else if (command === 'resolve') {
  const commentIds = args.slice(1);
  if (commentIds.length === 0) {
    console.error('Usage: node get-review-comments.js resolve <comment-id-1> [comment-id-2] ...');
    process.exit(1);
  }
  resolveComments(commentIds).then(results => {
    const resolved = results.filter(r => r.success).length;
    console.log(`✓ Resolved ${resolved}/${commentIds.length} comment(s)`);
    console.log(JSON.stringify(results, null, 2));
  });
} else {
  console.log('Usage:');
  console.log('  node get-review-comments.js by-path <spec-path>');
  console.log('  node get-review-comments.js by-project <repo-owner> <repo-name>');
  console.log('  node get-review-comments.js by-change <change-id>');
  console.log('  node get-review-comments.js resolve <comment-id-1> [comment-id-2] ...');
}
