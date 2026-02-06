const { createClient } = require('@supabase/supabase-js')
require('dotenv').config()

// Read credentials from environment variables
const supabaseUrl = process.env.SUPABASE_URL
const supabaseKey = process.env.SUPABASE_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY

if (!supabaseUrl || !supabaseKey) {
  console.error('❌ Error: SUPABASE_URL and SUPABASE_KEY environment variables are required')
  console.error('   Set these in .env file or shell environment.')
  console.error('   See README.md for configuration instructions.')
  process.exit(1)
}

/**
 * Query checkpoint and its comments from Supabase
 * 
 * Supports multiple query strategies:
 * 1. By file path (gets latest checkpoint for artifact)
 * 2. By git commit SHA
 * 3. By checkpoint ID (direct)
 */
async function queryCheckpointComments(options) {
  const supabase = createClient(supabaseUrl, supabaseKey)
  
  let checkpoint = null
  let artifact = null
  
  console.error('🔍 Querying checkpoint with options:', JSON.stringify(options, null, 2))
  
  // Strategy 1: By file path (works for both feature branch and main)
  // Query checkpoints directly instead of going through artifacts
  if (options.filePath && !options.commitSHA) {
    console.error(`📁 Looking up latest checkpoint by file path: ${options.filePath}`)
    
    // Get latest checkpoint for this file (works for both Change and Artifact)
    const { data: checkpointData, error: cpError } = await supabase
      .from('checkpoints')
      .select(`
        *,
        artifacts!checkpoints_artifact_id_fkey(file_path, project_id)
      `)
      .eq('artifacts.file_path', options.filePath)
      .order('created_at', { ascending: false })
      .limit(1)
      .single()
    
    if (cpError || !checkpointData) {
      throw new Error(`No checkpoint found for file: ${options.filePath}. File may not have been pushed yet or webhook is still processing.`)
    }
    
    checkpoint = checkpointData
    artifact = checkpointData.artifacts
    
    console.error(`✓ Found checkpoint: ${checkpoint.id}`)
    console.error(`  Branch: ${checkpoint.git_branch}`)
    console.error(`  Commit: ${checkpoint.git_commit_sha.substring(0, 8)}`)
  }
  
  // Strategy 2: By commit SHA + file path (RECOMMENDED for /specledger.revise)
  // This works for BOTH feature branch (Change) and main branch (Artifact)
  else if (options.commitSHA && options.filePath) {
    console.error(`🔗 Looking up checkpoint by commit SHA + file path`)
    console.error(`  Commit: ${options.commitSHA}`)
    console.error(`  File: ${options.filePath}`)
    
    // Query checkpoints directly by commit SHA and join with artifacts
    // This works because checkpoint is created for both Change and Artifact workflows
    const { data: checkpointData, error: cpError } = await supabase
      .from('checkpoints')
      .select(`
        *,
        artifacts!checkpoints_artifact_id_fkey(id, file_path, project_id),
        changes!checkpoints_change_id_fkey(id, branch_name, status)
      `)
      .eq('git_commit_sha', options.commitSHA)
    
    if (cpError) {
      throw new Error(`Failed to query checkpoints: ${cpError.message}`)
    }
    
    if (!checkpointData || checkpointData.length === 0) {
      throw new Error(`No checkpoints found for commit SHA: ${options.commitSHA}. Webhook may still be processing (wait 1-2 minutes).`)
    }
    
    // Find the checkpoint matching the file path
    // Check artifacts.file_path because that's where the path is stored
    const matchingCheckpoint = checkpointData.find(cp => {
      // The file path might be in artifacts table
      if (cp.artifacts?.file_path === options.filePath) {
        return true
      }
      
      // For feature branch, checkpoint is linked to change but artifact still has file_path
      // We need to check if any checkpoint in this commit matches the file
      return false
    })
    
    if (!matchingCheckpoint) {
      console.error(`Available checkpoints in this commit:`)
      checkpointData.forEach(cp => {
        console.error(`  - ${cp.artifacts?.file_path || 'no artifact'} (checkpoint: ${cp.id.substring(0, 8)})`)
      })
      throw new Error(`No checkpoint found for file "${options.filePath}" in commit ${options.commitSHA}`)
    }
    
    checkpoint = matchingCheckpoint
    artifact = matchingCheckpoint.artifacts
    
    // Log which workflow this is (Change vs Artifact)
    if (matchingCheckpoint.changes) {
      console.error(`✓ Found checkpoint in Change workflow (feature branch)`)
      console.error(`  Change: ${matchingCheckpoint.changes.id}`)
      console.error(`  Branch: ${matchingCheckpoint.changes.branch_name}`)
      console.error(`  Status: ${matchingCheckpoint.changes.status}`)
    } else if (matchingCheckpoint.artifacts) {
      console.error(`✓ Found checkpoint in Artifact workflow (main branch)`)
      console.error(`  Artifact: ${matchingCheckpoint.artifacts.id}`)
    }
  }
  
  // Strategy 3: By commit SHA only (returns all files)
  else if (options.commitSHA) {
    console.error(`🔗 Looking up ALL checkpoints by commit SHA: ${options.commitSHA}`)
    
    const { data: checkpointData, error: cpError } = await supabase
      .from('checkpoints')
      .select('*, artifacts!checkpoints_artifact_id_fkey(file_path, project_id)')
      .eq('git_commit_sha', options.commitSHA)
    
    if (cpError || !checkpointData || checkpointData.length === 0) {
      throw new Error(`No checkpoints found for commit SHA: ${options.commitSHA}`)
    }
    
    // Return all checkpoints (multi-file mode)
    // This will be handled differently in the return section
    console.error(`✓ Found ${checkpointData.length} checkpoint(s)`)
    checkpoint = checkpointData // Array instead of single object
    artifact = checkpointData[0].artifacts
  }
  
  // Strategy 3: By checkpoint ID (direct)
  else if (options.checkpointId) {
    console.error(`🎯 Looking up checkpoint by ID: ${options.checkpointId}`)
    
    const { data: cp, error: cpError } = await supabase
      .from('checkpoints')
      .select('*, artifacts!checkpoints_artifact_id_fkey(file_path, project_id)')
      .eq('id', options.checkpointId)
      .single()
    
    if (cpError || !cp) {
      throw new Error(`Checkpoint not found: ${options.checkpointId}`)
    }
    
    checkpoint = cp
    artifact = cp.artifacts
  }
  
  else {
    throw new Error('Must provide one of: --filePath, --commitSHA + --filePath, or --checkpointId')
  }
  
  // Handle multi-checkpoint mode (when only commitSHA provided)
  if (Array.isArray(checkpoint)) {
    console.error(`📦 Processing ${checkpoint.length} files from commit`)
    
    const results = []
    
    for (const cp of checkpoint) {
      console.error(`\n📄 Processing: ${cp.artifacts?.file_path}`)
      
      // Fetch comments for this checkpoint
      const { data: comments, error: commentsError } = await supabase
        .from('comments')
        .select('*')
        .eq('checkpoint_id', cp.id)
        .eq('is_resolved', false)
        .order('line_start', { ascending: true })
      
      if (commentsError) {
        console.error(`  ⚠️ Failed to fetch comments: ${commentsError.message}`)
        continue
      }
      
      console.error(`  ✓ Found ${comments.length} unresolved comment(s)`)
      
      // Fetch content
      const contentResponse = await fetch(cp.git_raw_url)
      if (!contentResponse.ok) {
        console.error(`  ⚠️ Failed to fetch content: ${contentResponse.statusText}`)
        continue
      }
      
      const content = await contentResponse.text()
      
      results.push({
        checkpoint: {
          id: cp.id,
          git_commit_sha: cp.git_commit_sha,
          git_branch: cp.git_branch,
          git_blob_url: cp.git_blob_url,
          git_raw_url: cp.git_raw_url,
          author_name: cp.author_name,
          author_email: cp.author_email,
          message: cp.message,
          created_at: cp.created_at
        },
        artifact: {
          file_path: cp.artifacts?.file_path,
          project_id: cp.artifacts?.project_id
        },
        comments: comments.map(c => ({
          id: c.id,
          content: c.content,
          line_start: c.line_start,
          line_end: c.line_end,
          author_name: c.author_name,
          author_id: c.author_id,
          created_at: c.created_at
        })),
        content: content
      })
    }
    
    return results
  }
  
  // Single checkpoint mode
  console.error(`✓ Found checkpoint: ${checkpoint.id}`)
  console.error(`  Branch: ${checkpoint.git_branch}`)
  console.error(`  Commit: ${checkpoint.git_commit_sha.substring(0, 8)}`)
  console.error(`  Author: ${checkpoint.author_name}`)
  
  // Fetch comments for this checkpoint
  console.error(`💬 Fetching comments...`)
  
  const { data: comments, error: commentsError } = await supabase
    .from('comments')
    .select('*')
    .eq('checkpoint_id', checkpoint.id)
    .eq('is_resolved', false)
    .order('line_start', { ascending: true })
  
  if (commentsError) {
    throw new Error(`Failed to fetch comments: ${commentsError.message}`)
  }
  
  console.error(`✓ Found ${comments.length} unresolved comment(s)`)
  
  // Fetch checkpoint content from git_raw_url
  console.error(`📥 Fetching checkpoint content from GitHub...`)
  
  const contentResponse = await fetch(checkpoint.git_raw_url)
  if (!contentResponse.ok) {
    throw new Error(`Failed to fetch checkpoint content: ${contentResponse.statusText}`)
  }
  
  const content = await contentResponse.text()
  console.error(`✓ Fetched ${content.length} bytes of content`)
  
  return {
    checkpoint: {
      id: checkpoint.id,
      git_commit_sha: checkpoint.git_commit_sha,
      git_branch: checkpoint.git_branch,
      git_blob_url: checkpoint.git_blob_url,
      git_raw_url: checkpoint.git_raw_url,
      author_name: checkpoint.author_name,
      author_email: checkpoint.author_email,
      message: checkpoint.message,
      created_at: checkpoint.created_at
    },
    artifact: {
      file_path: artifact?.file_path || options.filePath,
      project_id: artifact?.project_id
    },
    comments: comments.map(c => ({
      id: c.id,
      content: c.content,
      line_start: c.line_start,
      line_end: c.line_end,
      author_name: c.author_name,
      author_id: c.author_id,
      created_at: c.created_at
    })),
    content: content
  }
}

/**
 * Mark comments as resolved
 */
async function resolveComments(commentIds) {
  const supabase = createClient(supabaseUrl, supabaseKey)
  
  console.error(`✓ Marking ${commentIds.length} comment(s) as resolved...`)
  
  const { error } = await supabase
    .from('comments')
    .update({ 
      is_resolved: true,
      updated_at: new Date().toISOString()
    })
    .in('id', commentIds)
  
  if (error) {
    throw new Error(`Failed to mark comments as resolved: ${error.message}`)
  }
  
  console.error(`✓ Comments marked as resolved`)
}

// ============================================================================
// CLI INTERFACE
// ============================================================================

const args = process.argv.slice(2)
const command = args[0]

if (command === 'query') {
  // Parse query options
  const options = {}
  for (let i = 1; i < args.length; i += 2) {
    const key = args[i].replace(/^--/, '')
    const value = args[i + 1]
    options[key] = value
  }
  
  queryCheckpointComments(options)
    .then(result => {
      // Output JSON to stdout (for PowerShell to consume)
      console.log(JSON.stringify(result, null, 2))
    })
    .catch(err => {
      console.error(`❌ Error: ${err.message}`)
      process.exit(1)
    })
}
else if (command === 'resolve') {
  // Parse comment IDs
  const commentIds = args.slice(1).filter(arg => !arg.startsWith('--'))
  
  if (commentIds.length === 0) {
    console.error('Usage: node query-checkpoint-comments.js resolve <comment-id-1> <comment-id-2> ...')
    process.exit(1)
  }
  
  resolveComments(commentIds)
    .then(() => {
      console.log(JSON.stringify({ success: true, resolved: commentIds.length }))
    })
    .catch(err => {
      console.error(`❌ Error: ${err.message}`)
      process.exit(1)
    })
}
else {
  console.error('Usage:')
  console.error('  Query single file:')
  console.error('    node query-checkpoint-comments.js query --commitSHA <sha> --filePath <path>')
  console.error('    node query-checkpoint-comments.js query --filePath <path>')
  console.error('    node query-checkpoint-comments.js query --checkpointId <id>')
  console.error('')
  console.error('  Query all files in commit:')
  console.error('    node query-checkpoint-comments.js query --commitSHA <sha>')
  console.error('')
  console.error('  Resolve comments:')
  console.error('    node query-checkpoint-comments.js resolve <comment-id-1> <comment-id-2> ...')
  process.exit(1)
}
